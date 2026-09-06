
try:
    import platform
    import mlx_whisper  # noqa: F401 -- import itself is the availability probe
    import mlx
    print("DEBUG: HAS_MLX=True")
    print(f"DEBUG: Platform={platform.system()}")
    print(f"DEBUG: Machine={platform.machine()}")
    print(f"DEBUG: MLX Version={mlx.__version__}")
except ImportError as e:
    print(f"DEBUG: ImportError={e}")
except Exception as e:
    print(f"DEBUG: Exception={e}")
