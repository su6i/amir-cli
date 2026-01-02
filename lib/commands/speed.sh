#!/bin/bash

run_speed() {
    speed() {
        echo "⏳ Testing Network Quality..."
        networkQuality 2>/dev/null || echo "Command not available on this system."
    }
    speed
}
