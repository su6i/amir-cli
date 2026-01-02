#!/bin/bash

run_weather() {
    weather() {
        local city=${1:-Montpellier}
        curl -s "wttr.in/${city}?0m2t" 
    }
    weather "$@"
}
