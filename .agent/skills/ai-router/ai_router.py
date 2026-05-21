"""
Professional AI Model Router
Intelligently routes requests between Claude Opus 4.6 and DeepSeek
with cost optimization, caching, monitoring, and fallback strategies.
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from functools import wraps
import anthropic
import httpx


# ============================================================================
# Configuration & Types
# ============================================================================

class ModelType(Enum):
    """Available AI models (updated 2026-05-20)"""
    CLAUDE_OPUS = "claude-opus-4-7"
    CLAUDE_SONNET = "claude-sonnet-4-6"
    CLAUDE_HAIKU = "claude-haiku-4-5-20251001"
    DEEPSEEK_FLASH = "deepseek-v4-flash"   # replaces deepseek-chat + deepseek-reasoner
    DEEPSEEK_PRO = "deepseek-v4-pro"       # replaces deepseek-coder for complex tasks


class TaskComplexity(Enum):
    """Task complexity levels for routing decisions"""
    TRIVIAL = 1      # Boilerplate, simple formatting
    SIMPLE = 2       # Basic CRUD, standard patterns
    MODERATE = 3     # Business logic, multi-file changes
    COMPLEX = 4      # Architecture decisions, optimization
    CRITICAL = 5     # Production issues, security-critical


@dataclass
class ModelConfig:
    """Configuration for a specific model"""
    name: str
    api_key: str
    base_url: Optional[str] = None
    input_cost_per_1m: float = 0.0  # USD per 1M tokens
    output_cost_per_1m: float = 0.0
    max_tokens: int = 8192
    timeout: int = 120
    max_retries: int = 3
    rate_limit_per_minute: int = 50


@dataclass
class RoutingConfig:
    """Configuration for routing logic"""
    # Complexity thresholds for model selection
    deepseek_max_complexity: int = 2
    haiku_max_complexity: int = 3
    sonnet_max_complexity: int = 4
    
    # Cost optimization
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    enable_cost_tracking: bool = True
    
    # Fallback strategy
    enable_fallback: bool = True
    fallback_on_error: bool = True
    
    # Performance
    max_concurrent_requests: int = 10
    request_timeout: int = 120


@dataclass
class RequestMetrics:
    """Metrics for a single request"""
    model_used: ModelType
    complexity_score: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    cache_hit: bool
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None


# ============================================================================
# Complexity Analyzer
# ============================================================================

class ComplexityAnalyzer:
    """Analyzes task complexity to determine appropriate model"""
    
    # Keywords indicating complexity levels
    COMPLEXITY_INDICATORS = {
        TaskComplexity.TRIVIAL: [
            'format', 'indent', 'comment', 'rename', 'import',
            'boilerplate', 'template', 'scaffold'
        ],
        TaskComplexity.SIMPLE: [
            'crud', 'getter', 'setter', 'validate', 'parse',
            'convert', 'map', 'filter', 'simple test'
        ],
        TaskComplexity.MODERATE: [
            'implement', 'refactor', 'optimize', 'business logic',
            'api endpoint', 'database', 'integration', 'middleware'
        ],
        TaskComplexity.COMPLEX: [
            'architecture', 'design pattern', 'algorithm',
            'performance', 'scalability', 'security', 'complex test',
            'distributed', 'concurrency', 'async'
        ],
        TaskComplexity.CRITICAL: [
            'bug fix production', 'security vulnerability', 'data loss',
            'critical bug', 'emergency', 'zero-day', 'exploit'
        ]
    }
    
    @staticmethod
    def analyze(prompt: str, context: Optional[Dict[str, Any]] = None) -> Tuple[TaskComplexity, float]:
        """
        Analyze prompt complexity
        
        Returns:
            Tuple of (TaskComplexity, confidence_score)
        """
        prompt_lower = prompt.lower()
        scores = {complexity: 0.0 for complexity in TaskComplexity}
        
        # Keyword-based scoring
        for complexity, keywords in ComplexityAnalyzer.COMPLEXITY_INDICATORS.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    scores[complexity] += 1.0
        
        # Context-based adjustments
        if context:
            # Large codebases increase complexity
            if context.get('file_count', 0) > 10:
                scores[TaskComplexity.COMPLEX] += 1.0
            
            # Production environment increases complexity
            if context.get('environment') == 'production':
                scores[TaskComplexity.CRITICAL] += 2.0
            
            # Time pressure increases complexity
            if context.get('urgent'):
                scores[TaskComplexity.CRITICAL] += 1.0
        
        # Length-based complexity (longer prompts often = more complex)
        word_count = len(prompt.split())
        if word_count > 200:
            scores[TaskComplexity.COMPLEX] += 0.5
        elif word_count > 100:
            scores[TaskComplexity.MODERATE] += 0.5
        
        # Determine final complexity
        if not any(scores.values()):
            return TaskComplexity.SIMPLE, 0.5  # Default
        
        max_complexity = max(scores, key=scores.get)
        confidence = min(scores[max_complexity] / 3.0, 1.0)  # Normalize to 0-1
        
        return max_complexity, confidence


# ============================================================================
# Cache Manager
# ============================================================================

class CacheManager:
    """Manages response caching to reduce costs"""
    
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._lock = asyncio.Lock()
    
    def _get_cache_key(self, prompt: str, model: ModelType, **kwargs) -> str:
        """Generate cache key from request parameters"""
        cache_data = f"{prompt}:{model.value}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.sha256(cache_data.encode()).hexdigest()
    
    async def get(self, prompt: str, model: ModelType, **kwargs) -> Optional[Any]:
        """Retrieve cached response if available and fresh"""
        async with self._lock:
            cache_key = self._get_cache_key(prompt, model, **kwargs)
            if cache_key in self._cache:
                response, timestamp = self._cache[cache_key]
                if datetime.now() - timestamp < timedelta(seconds=self.ttl_seconds):
                    return response
                else:
                    # Expired, remove from cache
                    del self._cache[cache_key]
            return None
    
    async def set(self, prompt: str, model: ModelType, response: Any, **kwargs):
        """Store response in cache"""
        async with self._lock:
            cache_key = self._get_cache_key(prompt, model, **kwargs)
            self._cache[cache_key] = (response, datetime.now())
    
    async def clear_expired(self):
        """Remove expired entries from cache"""
        async with self._lock:
            now = datetime.now()
            expired_keys = [
                key for key, (_, timestamp) in self._cache.items()
                if now - timestamp >= timedelta(seconds=self.ttl_seconds)
            ]
            for key in expired_keys:
                del self._cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'total_entries': len(self._cache),
            'memory_usage_mb': len(str(self._cache)) / (1024 * 1024)
        }


# ============================================================================
# Cost Tracker
# ============================================================================

class CostTracker:
    """Tracks API usage costs and provides analytics"""
    
    def __init__(self):
        self._metrics: List[RequestMetrics] = []
        self._lock = asyncio.Lock()
    
    async def record(self, metrics: RequestMetrics):
        """Record a request's metrics"""
        async with self._lock:
            self._metrics.append(metrics)
    
    async def get_summary(self, time_window: Optional[timedelta] = None) -> Dict[str, Any]:
        """Get cost summary for specified time window"""
        async with self._lock:
            if time_window:
                cutoff = datetime.now() - time_window
                metrics = [m for m in self._metrics if m.timestamp >= cutoff]
            else:
                metrics = self._metrics
            
            if not metrics:
                return {'total_requests': 0, 'total_cost': 0.0}
            
            total_cost = sum(m.cost_usd for m in metrics)
            total_requests = len(metrics)
            cache_hits = sum(1 for m in metrics if m.cache_hit)
            errors = sum(1 for m in metrics if m.error)
            
            # Per-model breakdown
            model_costs = {}
            for model in ModelType:
                model_metrics = [m for m in metrics if m.model_used == model]
                if model_metrics:
                    model_costs[model.value] = {
                        'requests': len(model_metrics),
                        'cost': sum(m.cost_usd for m in model_metrics),
                        'avg_latency_ms': sum(m.latency_ms for m in model_metrics) / len(model_metrics)
                    }
            
            return {
                'total_requests': total_requests,
                'total_cost': round(total_cost, 4),
                'cache_hit_rate': round(cache_hits / total_requests, 2) if total_requests else 0,
                'error_rate': round(errors / total_requests, 2) if total_requests else 0,
                'avg_cost_per_request': round(total_cost / total_requests, 4) if total_requests else 0,
                'model_breakdown': model_costs,
                'time_window': str(time_window) if time_window else 'all_time'
            }
    
    async def estimate_monthly_cost(self, requests_per_day: int) -> Dict[str, float]:
        """Estimate monthly cost based on recent usage patterns"""
        async with self._lock:
            if not self._metrics:
                return {'estimated_monthly_cost': 0.0}
            
            recent_metrics = self._metrics[-100:]  # Last 100 requests
            avg_cost = sum(m.cost_usd for m in recent_metrics) / len(recent_metrics)
            
            daily_cost = avg_cost * requests_per_day
            monthly_cost = daily_cost * 30
            
            return {
                'avg_cost_per_request': round(avg_cost, 4),
                'estimated_daily_cost': round(daily_cost, 2),
                'estimated_monthly_cost': round(monthly_cost, 2)
            }


# ============================================================================
# Model Clients
# ============================================================================

class ModelClient(ABC):
    """Abstract base class for model clients"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> Tuple[str, int, int]:
        """
        Generate response from model
        
        Returns:
            Tuple of (response_text, input_tokens, output_tokens)
        """
        pass
    
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for token usage"""
        input_cost = (input_tokens / 1_000_000) * self.config.input_cost_per_1m
        output_cost = (output_tokens / 1_000_000) * self.config.output_cost_per_1m
        return input_cost + output_cost


class ClaudeClient(ModelClient):
    """Client for Anthropic Claude models"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.client = anthropic.AsyncAnthropic(
            api_key=config.api_key,
            timeout=config.timeout
        )
    
    async def generate(self, prompt: str, **kwargs) -> Tuple[str, int, int]:
        """Generate response using Claude API"""
        max_tokens = kwargs.get('max_tokens', self.config.max_tokens)
        temperature = kwargs.get('temperature', 1.0)
        system = kwargs.get('system', None)
        
        messages = [{"role": "user", "content": prompt}]
        
        response = await self.client.messages.create(
            model=self.config.name,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
            system=system if system else anthropic.NOT_GIVEN
        )
        
        response_text = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        
        return response_text, input_tokens, output_tokens


class DeepSeekClient(ModelClient):
    """Client for DeepSeek models"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.client = httpx.AsyncClient(
            base_url=config.base_url or "https://api.deepseek.com/v1",
            timeout=config.timeout,
            headers={"Authorization": f"Bearer {config.api_key}"}
        )
    
    async def generate(self, prompt: str, **kwargs) -> Tuple[str, int, int]:
        """Generate response using DeepSeek API"""
        max_tokens = kwargs.get('max_tokens', self.config.max_tokens)
        temperature = kwargs.get('temperature', 1.0)
        
        payload = {
            "model": self.config.name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        
        response_text = data['choices'][0]['message']['content']
        input_tokens = data['usage']['prompt_tokens']
        output_tokens = data['usage']['completion_tokens']
        
        return response_text, input_tokens, output_tokens
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()


# ============================================================================
# Circuit Breaker
# ============================================================================

class CircuitBreaker:
    """Circuit breaker pattern for handling service failures"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open
    
    def record_success(self):
        """Record successful request"""
        self.failure_count = 0
        self.state = 'closed'
    
    def record_failure(self):
        """Record failed request"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
    
    def can_request(self) -> bool:
        """Check if requests are allowed"""
        if self.state == 'closed':
            return True
        
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'half_open'
                return True
            return False
        
        # half_open state
        return True


# ============================================================================
# AI Router
# ============================================================================

class AIRouter:
    """
    Professional AI Router that intelligently routes requests
    between multiple AI models with cost optimization
    """
    
    def __init__(
        self,
        model_configs: Dict[ModelType, ModelConfig],
        routing_config: Optional[RoutingConfig] = None
    ):
        self.model_configs = model_configs
        self.routing_config = routing_config or RoutingConfig()
        
        # Initialize clients
        self.clients: Dict[ModelType, ModelClient] = {}
        self._initialize_clients()
        # Note: DEEPSEEK_FLASH supports thinking mode via extra_body={"thinking": {"type": "enabled", "budget_tokens": N}}
        
        # Initialize components
        self.cache = CacheManager(self.routing_config.cache_ttl_seconds) if self.routing_config.enable_caching else None
        self.cost_tracker = CostTracker() if self.routing_config.enable_cost_tracking else None
        self.complexity_analyzer = ComplexityAnalyzer()
        
        # Circuit breakers per model
        self.circuit_breakers = {model: CircuitBreaker() for model in ModelType}
        
        # Semaphore for concurrency control
        self.semaphore = asyncio.Semaphore(self.routing_config.max_concurrent_requests)
        
        # Logging
        self._setup_logging()
    
    def _initialize_clients(self):
        """Initialize model clients based on configuration"""
        for model_type, config in self.model_configs.items():
            if model_type in [ModelType.CLAUDE_OPUS, ModelType.CLAUDE_SONNET, ModelType.CLAUDE_HAIKU]:
                self.clients[model_type] = ClaudeClient(config)
            elif model_type in [ModelType.DEEPSEEK_FLASH, ModelType.DEEPSEEK_PRO]:
                self.clients[model_type] = DeepSeekClient(config)
    
    def _setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('AIRouter')
    
    def select_model(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        force_model: Optional[ModelType] = None
    ) -> ModelType:
        """
        Select appropriate model based on task complexity
        
        Args:
            prompt: The user's prompt
            context: Additional context for complexity analysis
            force_model: Override automatic selection
        
        Returns:
            Selected ModelType
        """
        if force_model:
            return force_model
        
        complexity, confidence = self.complexity_analyzer.analyze(prompt, context)
        
        self.logger.info(
            f"Complexity analysis: {complexity.name} (confidence: {confidence:.2f})"
        )
        
        # Route based on complexity
        if complexity.value <= self.routing_config.deepseek_max_complexity:
            # Try DeepSeek first (cheaper): Flash for simple, Pro for moderate
            if complexity.value <= 1 and ModelType.DEEPSEEK_FLASH in self.clients:
                return ModelType.DEEPSEEK_FLASH
            elif ModelType.DEEPSEEK_PRO in self.clients:
                return ModelType.DEEPSEEK_PRO
        
        if complexity.value <= self.routing_config.haiku_max_complexity:
            if ModelType.CLAUDE_HAIKU in self.clients:
                return ModelType.CLAUDE_HAIKU
        
        if complexity.value <= self.routing_config.sonnet_max_complexity:
            if ModelType.CLAUDE_SONNET in self.clients:
                return ModelType.CLAUDE_SONNET
        
        # Default to most powerful model for critical tasks
        if ModelType.CLAUDE_OPUS in self.clients:
            return ModelType.CLAUDE_OPUS
        
        # Fallback to any available model
        return next(iter(self.clients.keys()))
    
    async def generate(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        force_model: Optional[ModelType] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate response with intelligent routing and fallback
        
        Args:
            prompt: User prompt
            context: Additional context
            force_model: Force specific model
            **kwargs: Additional parameters for generation
        
        Returns:
            Dict containing response and metadata
        """
        async with self.semaphore:
            start_time = time.time()
            
            # Check cache first
            selected_model = self.select_model(prompt, context, force_model)
            
            if self.cache:
                cached_response = await self.cache.get(prompt, selected_model, **kwargs)
                if cached_response:
                    self.logger.info(f"Cache hit for model {selected_model.value}")
                    return {
                        **cached_response,
                        'cache_hit': True,
                        'latency_ms': 0
                    }
            
            # Try primary model with circuit breaker
            response_data = await self._generate_with_fallback(
                prompt, selected_model, start_time, **kwargs
            )
            
            # Cache the response
            if self.cache and not response_data.get('error'):
                await self.cache.set(prompt, selected_model, response_data, **kwargs)
            
            return response_data
    
    async def _generate_with_fallback(
        self,
        prompt: str,
        primary_model: ModelType,
        start_time: float,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate with automatic fallback on failure"""
        models_to_try = [primary_model]
        
        # Add fallback models if enabled
        if self.routing_config.enable_fallback:
            fallback_order = [
                ModelType.CLAUDE_SONNET,
                ModelType.CLAUDE_HAIKU,
                ModelType.DEEPSEEK_PRO,
                ModelType.DEEPSEEK_FLASH,
            ]
            models_to_try.extend([m for m in fallback_order if m != primary_model and m in self.clients])
        
        last_error = None
        
        for model in models_to_try:
            # Check circuit breaker
            if not self.circuit_breakers[model].can_request():
                self.logger.warning(f"Circuit breaker open for {model.value}, skipping")
                continue
            
            try:
                client = self.clients[model]
                response_text, input_tokens, output_tokens = await client.generate(
                    prompt, **kwargs
                )
                
                # Success - record metrics
                latency_ms = (time.time() - start_time) * 1000
                cost = client.calculate_cost(input_tokens, output_tokens)
                
                self.circuit_breakers[model].record_success()
                
                metrics = RequestMetrics(
                    model_used=model,
                    complexity_score=0.0,  # Filled by caller
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    cache_hit=False
                )
                
                if self.cost_tracker:
                    await self.cost_tracker.record(metrics)
                
                self.logger.info(
                    f"Generated with {model.value}: {input_tokens}+{output_tokens} tokens, "
                    f"${cost:.4f}, {latency_ms:.0f}ms"
                )
                
                return {
                    'response': response_text,
                    'model': model.value,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'cost_usd': cost,
                    'latency_ms': latency_ms,
                    'cache_hit': False
                }
            
            except Exception as e:
                self.logger.error(f"Error with {model.value}: {str(e)}")
                self.circuit_breakers[model].record_failure()
                last_error = e
                
                if not self.routing_config.fallback_on_error:
                    raise
                
                continue
        
        # All models failed
        raise Exception(f"All models failed. Last error: {str(last_error)}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get router statistics"""
        stats = {
            'active_models': list(self.clients.keys()),
        }
        
        if self.cost_tracker:
            stats['cost_summary'] = await self.cost_tracker.get_summary()
            stats['cost_summary_24h'] = await self.cost_tracker.get_summary(
                timedelta(hours=24)
            )
        
        if self.cache:
            stats['cache_stats'] = self.cache.get_stats()
        
        # Circuit breaker states
        stats['circuit_breakers'] = {
            model.value: breaker.state
            for model, breaker in self.circuit_breakers.items()
        }
        
        return stats
    
    async def cleanup(self):
        """Cleanup resources"""
        for client in self.clients.values():
            if hasattr(client, 'client') and hasattr(client.client, 'aclose'):
                await client.client.aclose()


# ============================================================================
# Example Usage & Configuration
# ============================================================================

async def main():
    """Example usage of AI Router"""
    
    # Configure models (replace with your actual API keys)
    model_configs = {
        ModelType.CLAUDE_OPUS: ModelConfig(
            name="claude-opus-4-6",
            api_key="your-claude-api-key",
            input_cost_per_1m=5.0,
            output_cost_per_1m=25.0,
            max_tokens=8192
        ),
        ModelType.CLAUDE_SONNET: ModelConfig(
            name="claude-sonnet-4-5-20250929",
            api_key="your-claude-api-key",
            input_cost_per_1m=1.0,
            output_cost_per_1m=5.0,
            max_tokens=8192
        ),
        ModelType.DEEPSEEK_FLASH: ModelConfig(
            name="deepseek-v4-flash",
            api_key="your-deepseek-api-key",
            base_url="https://api.deepseek.com/v1",
            input_cost_per_1m=0.14,
            output_cost_per_1m=0.28,
            max_tokens=16384
        )
    }
    
    # Configure routing
    routing_config = RoutingConfig(
        deepseek_max_complexity=2,
        enable_caching=True,
        enable_fallback=True,
        max_concurrent_requests=10
    )
    
    # Initialize router
    router = AIRouter(model_configs, routing_config)
    
    try:
        # Example 1: Simple task (should use DeepSeek)
        print("\\n=== Example 1: Simple CRUD ===")
        response1 = await router.generate(
            "Write a simple CRUD function for a user model in Python"
        )
        print(f"Model used: {response1['model']}")
        print(f"Cost: ${response1['cost_usd']:.4f}")
        print(f"Response preview: {response1['response'][:100]}...")
        
        # Example 2: Complex task (should use Claude Opus)
        print("\\n=== Example 2: Complex Architecture ===")
        response2 = await router.generate(
            "Design a distributed microservices architecture for a high-traffic "
            "e-commerce platform with considerations for scalability and fault tolerance",
            context={'environment': 'production', 'urgent': True}
        )
        print(f"Model used: {response2['model']}")
        print(f"Cost: ${response2['cost_usd']:.4f}")
        
        # Example 3: Force specific model
        print("\\n=== Example 3: Force Model ===")
        response3 = await router.generate(
            "Explain dependency injection",
            force_model=ModelType.CLAUDE_HAIKU
        )
        print(f"Model used: {response3['model']}")
        
        # Get statistics
        print("\\n=== Statistics ===")
        stats = await router.get_stats()
        print(json.dumps(stats, indent=2, default=str))
        
        # Estimate monthly costs
        if router.cost_tracker:
            monthly_estimate = await router.cost_tracker.estimate_monthly_cost(
                requests_per_day=500
            )
            print("\\n=== Monthly Cost Estimate (500 requests/day) ===")
            print(json.dumps(monthly_estimate, indent=2))
    
    finally:
        await router.cleanup()


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
