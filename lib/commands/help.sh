#!/bin/bash

run_help() {
    print_header "Amir CLI Help"
    echo "Usage: $(basename "$0") <command> [args]"
    echo ""
    echo -e "${BOLD}Multimedia:${NC}"
    echo "  compress <file> [res] [q]    Compress video (Smart HEVC)"
    echo "  compress batch [res]         Batch compress videos in folder"
    echo "  mp3 <file> [bitrate]         Extract audio from video"
    echo "  img <file> [size]            Resize image"
    echo "  info <file>                  Show detailed file info"
    echo "  subtitle <file> [opts]       Generate subtitles (AI)"
    echo "  compress codecs              Show available HEVC codecs"
    
    echo ""
    echo -e "${BOLD}Utilities:${NC}"
    echo "  transfer <file>              Upload file to temporary hosting"
    echo "  qr <text> [out]              Generate QR code"
    echo "  short <url>                  Shorten URL"
    echo "  lock/unlock <file>           Encrypt/Decrypt file"
    echo "  pass [len]                   Generate secure password"
    echo "  clip <text|file>             Smart clipboard tool"
    echo "  clean                        Clean system cache/trash"
    echo "  speed                        Test internet speed"
    echo "  weather [city]               Show weather"
    
    echo ""
    echo -e "${BOLD}AI & Productivity:${NC}"
    echo "  chat <query>                 Ask Gemini/Gemma AI"
    echo "  code <request>               Generate/Refactor code with AI"
    echo "  todo [add/done]              Manage local todo list"
    echo "  dashboard                    Show system status dashboard"
    
    echo ""
    echo -e "${BOLD}System:${NC}"
    echo "  help                         Show this help"
    echo ""
}
