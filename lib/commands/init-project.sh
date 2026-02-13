#!/bin/bash

run_init_project() {
    # 1. Determine Paths
    # We want to link to the LIVE constitution repo.
    # Logic: Check Env Var -> Check Sibling Directory -> Error
    
    local LIVE_SOURCE=""
    
    # Check 1: AMIR_CONSTITUTION_PATH env var
    if [[ -n "$AMIR_CONSTITUTION_PATH" && -d "$AMIR_CONSTITUTION_PATH" ]]; then
        LIVE_SOURCE="$AMIR_CONSTITUTION_PATH"
    fi
    
    # Check 2: Sibling directory (assuming amir-cli and agent-constitution are in the same folder)
    if [[ -z "$LIVE_SOURCE" ]]; then
        local SIBLING="$SCRIPT_DIR/../agent-constitution"
        if [[ -d "$SIBLING" ]]; then
            LIVE_SOURCE="$(cd "$SIBLING" && pwd)"
        fi
    fi

    if [[ -z "$LIVE_SOURCE" ]]; then
        echo "❌ Error: Could not locate 'agent-constitution' repository."
        echo "   Checked: \$AMIR_CONSTITUTION_PATH and ../agent-constitution"
        return 1
    fi
    
    local SOURCE_ROOT="$LIVE_SOURCE"
    
    local TARGET_DIR=""
    local MODE=""

    if [[ -n "$1" ]]; then
        TARGET_DIR="$1"
        if [[ "$TARGET_DIR" == "." || "$TARGET_DIR" == "./" ]]; then
            MODE="UPDATE"
        else
            MODE="NEW"
        fi
    else
        TARGET_DIR="sample-project"
        MODE="DEFAULT"
    fi

    echo "⚡ Initiating Agent Constitution Injection..."
    echo "📍 Source Constitution: $SOURCE_ROOT"
    
    if [[ "$MODE" == "UPDATE" ]]; then
        echo "🔄 Mode: Update/Scaffold Current Directory"
        echo "🎯 Target: $(pwd)"
    else
        echo "✨ Mode: New Project"
        echo "🎯 Target: $TARGET_DIR"
    fi

    # 2. Safety Checks & Creation
    if [ ! -d "$TARGET_DIR" ]; then
        echo "📂 Creating new project directory: $TARGET_DIR"
        mkdir -p "$TARGET_DIR"
    fi

    if [ ! -d "$TARGET_DIR/.git" ]; then
        echo "⚠️  Warning: Target is not a git repository. Proceeding anyway..."
    fi

    # 3. Intelligent File Copy (Selective)
    echo "📂 Copying essential protocols..."

    # Function to copy specific files safely
    copy_file() {
        local src="$1"
        local dst="$2"
        
        # Ensure parent dir exists
        mkdir -p "$(dirname "$dst")"

        if [ -e "$dst" ]; then
            echo "   🔸 Backing up existing $(basename "$dst")..."
            mv "$dst" "$dst.bak"
        fi
        
        if [ -e "$src" ]; then
            cp -R "$src" "$dst"
            echo "   ✅ Installed $(basename "$dst")"
        else
            echo "   ⚠️  Source not found: $(basename "$src")"
        fi
    }

    # Create target structure
    mkdir -p "$TARGET_DIR/.cursor/rules"
    mkdir -p "$TARGET_DIR/.cursor/workflows"
    
    # --- SELECTIVE COPY LOGIC ---
    
    # Rules: Copy specific rules, rename global.mdc.md -> global.mdc if needed
    # We explicitly look for the correct file at source
    
    # Global Constitution
    if [[ -f "$SOURCE_ROOT/.cursor/rules/global.mdc" ]]; then
         copy_file "$SOURCE_ROOT/.cursor/rules/global.mdc" "$TARGET_DIR/.cursor/rules/global.mdc"
    elif [[ -f "$SOURCE_ROOT/.cursor/rules/global.mdc.md" ]]; then
         # Fix double extension on copy
         copy_file "$SOURCE_ROOT/.cursor/rules/global.mdc.md" "$TARGET_DIR/.cursor/rules/global.mdc"
    fi

    # Workflows: Copy essential workflows ONLY (avoid copying unrelated agent prompts)
    # Define the whitelist of workflows to copy
    ESSENTIAL_WORKFLOWS=(
        "init-project.md"
        "documentation.md"
        "ai-optimization.md"
        "quality-assurance.md"
        "social-media-showcase.md"
    )

    for wf in "${ESSENTIAL_WORKFLOWS[@]}"; do
        if [[ -f "$SOURCE_ROOT/.cursor/workflows/$wf" ]]; then
             copy_file "$SOURCE_ROOT/.cursor/workflows/$wf" "$TARGET_DIR/.cursor/workflows/$wf"
        fi
    done

    # Skills: Copy ALL skills
    if [[ -d "$SOURCE_ROOT/.cursor/skills" ]]; then
         copy_file "$SOURCE_ROOT/.cursor/skills" "$TARGET_DIR/.cursor/skills"
    fi

    # 4. Scaffold Standard Directories
    echo "🏗️  Creating standard directory structure..."
    DIRS=(
        "src"
        "tests"
        "docs"
        "assets"
        "lib"
        "Roadmap"  # Added Roadmap
        ".storage/temp"
        ".storage/data"
    )

    for dir in "${DIRS[@]}"; do
        TARGET_PATH="$TARGET_DIR/$dir"
        if [ ! -d "$TARGET_PATH" ]; then
            mkdir -p "$TARGET_PATH"
            echo "   ➕ Created $dir/"
        else
            echo "   🔸 Exists $dir/"
        fi
    done
    
    # Copy generic assets from Amir CLI itself (not Constitution repo)
    LOCAL_ASSETS="$LIB_DIR/../assets"
    if [[ -f "$LOCAL_ASSETS/linkedin_su6i.svg" ]]; then
        copy_file "$LOCAL_ASSETS/linkedin_su6i.svg" "$TARGET_DIR/assets/linkedin_su6i.svg"
    fi

    # 5. Comprehensive .gitignore
    GITIGNORE="$TARGET_DIR/.gitignore"
    
    # We overwrite the gitignore with the comprehensive standard, or append if it exists but is empty?
    # To be safe and ensure the standard, we will write it if it doesn't exist, or append missing sections if it does.
    # Given the user provided a full template, let's write it fresh if it's a new project, or append blindly if update.
    
    if [ ! -f "$GITIGNORE" ]; then
        echo "🛡️  Writing comprehensive .gitignore..."
        cat <<EOF > "$GITIGNORE"
# Created by https://www.toptal.com/developers/gitignore/api/python,visualstudiocode,pycharm,jupyternotebooks,macos,linux,windows,venv,virtualenv
# Edit at https://www.toptal.com/developers/gitignore?templates=python,visualstudiocode,pycharm,jupyternotebooks,macos,linux,windows,venv,virtualenv

### JupyterNotebooks ###
# gitignore template for Jupyter Notebooks
# website: http://jupyter.org/

.ipynb_checkpoints
*/.ipynb_checkpoints/*

# IPython
profile_default/
ipython_config.py

# Remove previous ipynb_checkpoints
#   git rm -r .ipynb_checkpoints/

### Linux ###
*~

# temporary files which can be created if a process still has a handle open of a deleted file
.fuse_hidden*

# KDE directory preferences
.directory

# Linux trash folder which might appear on any partition or disk
.Trash-*

# .nfs files are created when an open file is removed but is still being accessed
.nfs*

### macOS ###
# General
.DS_Store
.AppleDouble
.LSOverride

# Icon must end with two \r
Icon


# Thumbnails
._*

# Files that might appear in the root of a volume
.DocumentRevisions-V100
.fseventsd
.Spotlight-V100
.TemporaryItems
.Trashes
.VolumeIcon.icns
.com.apple.timemachine.donotpresent

# Directories potentially created on remote AFP share
.AppleDB
.AppleDesktop
Network Trash Folder
Temporary Items
.apdisk

### macOS Patch ###
# iCloud generated files
*.icloud

### PyCharm ###
# Covers JetBrains IDEs: IntelliJ, RubyMine, PhpStorm, AppCode, PyCharm, CLion, Android Studio, WebStorm and Rider
# Reference: https://intellij-support.jetbrains.com/hc/en-us/articles/206544839

# User-specific stuff
.idea/**/workspace.xml
.idea/**/tasks.xml
.idea/**/usage.statistics.xml
.idea/**/dictionaries
.idea/**/shelf

# AWS User-specific
.idea/**/aws.xml

# Generated files
.idea/**/contentModel.xml

# Sensitive or high-churn files
.idea/**/dataSources/
.idea/**/dataSources.ids
.idea/**/dataSources.local.xml
.idea/**/sqlDataSources.xml
.idea/**/dynamic.xml
.idea/**/uiDesigner.xml
.idea/**/dbnavigator.xml

# Gradle
.idea/**/gradle.xml
.idea/**/libraries

# Gradle and Maven with auto-import
# When using Gradle or Maven with auto-import, you should exclude module files,
# since they will be recreated, and may cause churn.  Uncomment if using
# auto-import.
# .idea/artifacts
# .idea/compiler.xml
# .idea/jarRepositories.xml
# .idea/modules.xml
# .idea/*.iml
# .idea/modules
# *.iml
# *.ipr

# CMake
cmake-build-*/

# Mongo Explorer plugin
.idea/**/mongoSettings.xml

# File-based project format
*.iws

# IntelliJ
out/

# mpeltonen/sbt-idea plugin
.idea_modules/

# JIRA plugin
atlassian-ide-plugin.xml

# Cursive Clojure plugin
.idea/replstate.xml

# SonarLint plugin
.idea/sonarlint/

# Crashlytics plugin (for Android Studio and IntelliJ)
com_crashlytics_export_strings.xml
crashlytics.properties
crashlytics-build.properties
fabric.properties

# Editor-based Rest Client
.idea/httpRequests

# Android studio 3.1+ serialized cache file
.idea/caches/build_file_checksums.ser

### PyCharm Patch ###
# Comment Reason: https://github.com/joeblau/gitignore.io/issues/186#issuecomment-215987721

# *.iml
# modules.xml
# .idea/misc.xml
# *.ipr

# Sonarlint plugin
# https://plugins.jetbrains.com/plugin/7973-sonarlint
.idea/**/sonarlint/

# SonarQube Plugin
# https://plugins.jetbrains.com/plugin/7238-sonarqube-community-plugin
.idea/**/sonarIssues.xml

# Markdown Navigator plugin
# https://plugins.jetbrains.com/plugin/7896-markdown-navigator-enhanced
.idea/**/markdown-navigator.xml
.idea/**/markdown-navigator-enh.xml
.idea/**/markdown-navigator/

# Cache file creation bug
# See https://youtrack.jetbrains.com/issue/JBR-2257
.idea/\$CACHE_FILE$

# CodeStream plugin
# https://plugins.jetbrains.com/plugin/12206-codestream
.idea/codestream.xml

# Azure Toolkit for IntelliJ plugin
# https://plugins.jetbrains.com/plugin/8053-azure-toolkit-for-intellij
.idea/**/azureSettings.xml

### Python ###
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*\$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
#  Usually these files are written by a python script from a template
#  before PyInstaller builds the exe, so as to inject date/other infos into it.
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
cover/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
.pybuilder/
target/

# Jupyter Notebook

# IPython

# pyenv
#   For a library or package, you might want to ignore these files since the code is
#   intended to run in multiple environments; otherwise, check them in:
# .python-version

# pipenv
#   According to pypa/pipenv#598, it is recommended to include Pipfile.lock in version control.
#   However, in case of collaboration, if having platform-specific dependencies or dependencies
#   having no cross-platform support, pipenv may install dependencies that don't work, or not
#   install all needed dependencies.
#Pipfile.lock

# poetry
#   Similar to Pipfile.lock, it is generally recommended to include poetry.lock in version control.
#   This is especially recommended for binary packages to ensure reproducibility, and is more
#   commonly ignored for libraries.
#   https://python-poetry.org/docs/basic-usage/#commit-your-poetrylock-file-to-version-control
#poetry.lock

# pdm
#   Similar to Pipfile.lock, it is generally recommended to include pdm.lock in version control.
#pdm.lock
#   pdm stores project-wide configurations in .pdm.toml, but it is recommended to not include it
#   in version control.
#   https://pdm.fming.dev/#use-with-ide
.pdm.toml

# PEP 582; used by e.g. github.com/David-OConnor/pyflow and github.com/pdm-project/pdm
__pypackages__/

# Celery stuff
celerybeat-schedule
celerybeat.pid

# SageMath parsed files
*.sage.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Pyre type checker
.pyre/

# pytype static type analyzer
.pytype/

# Cython debug symbols
cython_debug/

# PyCharm
#  JetBrains specific template is maintained in a separate JetBrains.gitignore that can
#  be found at https://github.com/github/gitignore/blob/main/Global/JetBrains.gitignore
#  and can be added to the global gitignore or merged into this file.  For a more nuclear
#  option (not recommended) you can uncomment the following to ignore the entire idea folder.
#.idea/

### Python Patch ###
# Poetry local configuration file - https://python-poetry.org/docs/configuration/#local-configuration
poetry.toml

# ruff
.ruff_cache/

# LSP config files
pyrightconfig.json

### venv ###
# Virtualenv
# http://iamzed.com/2009/05/07/a-primer-on-virtualenv/
[Bb]in
[Ii]nclude
[Ll]ib
[Ll]ib64
[Ll]ocal
[Ss]cripts
pyvenv.cfg
pip-selfcheck.json

### VirtualEnv ###
# Virtualenv
# http://iamzed.com/2009/05/07/a-primer-on-virtualenv/

### VisualStudioCode ###
.vscode/*
!.vscode/settings.json
!.vscode/tasks.json
!.vscode/launch.json
!.vscode/extensions.json
!.vscode/*.code-snippets

# Local History for Visual Studio Code
.history/

# Built Visual Studio Code Extensions
*.vsix

### VisualStudioCode Patch ###
# Ignore all local history of files
.history
.ionide

### Windows ###
# Windows thumbnail cache files
Thumbs.db
Thumbs.db:encryptable
ehthumbs.db
ehthumbs_vista.db

# Dump file
*.stackdump

# Folder config file
[Dd]esktop.ini

# Recycle Bin used on file shares
$RECYCLE.BIN/

# Windows Installer files
*.cab
*.msi
*.msix
*.msm
*.msp

# Windows shortcuts
*.lnk

# End of https://www.toptal.com/developers/gitignore/api/python,visualstudiocode,pycharm,jupyternotebooks,macos,linux,windows,venv,virtualenv

# Project Specific
Roadmap/
EOF
    else
        echo "🛡️  .gitignore exists. Appending critical project-specific rules if missing..."
        # Just ensure 'Roadmap/' is there if file exists to avoid messing up user's custom gitignore 
        if ! grep -qF "Roadmap/" "$GITIGNORE"; then
            echo "" >> "$GITIGNORE"
            echo "# Project Specific" >> "$GITIGNORE"
            echo "Roadmap/" >> "$GITIGNORE"
            echo "   ➕ Added Roadmap/"
        fi
    fi

    # 6. Git Add
    if [ -d "$TARGET_DIR/.git" ]; then
        echo "💾 Staging changes..."
        local CURRENT_PWD=$(pwd)
        cd "$TARGET_DIR" || return 1
        
        if command -v git &> /dev/null; then
            git add .cursor/ .gitignore src/ tests/ docs/ assets/ lib/ Roadmap/
            echo "   ✅ Files flagged for commit."
        else
             echo "⚠️  Git not found, skipping stage."
        fi
        cd "$CURRENT_PWD"
    else
        echo "ℹ️  Skipped git add (not a repo)."
    fi

    echo "🎉 Constitution Installed! This project is now strictly Agent-Governed."
    echo "📜 Please review the Workflows in .cursor/workflows/"
}
