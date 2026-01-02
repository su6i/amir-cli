#!/bin/bash

run_pass() {
    pass() {
        local len=${1:-16}
        local p=$(LC_ALL=C tr -dc 'A-Za-z0-9!@#$%^&*()_+' < /dev/urandom | head -c "$len")
        echo "$p" | pbcopy 2>/dev/null || echo -n "$p" | xclip -selection clipboard 2>/dev/null
        echo "🔑 Password ($len chars) copied: $p"
    }
    pass "$@"
}
