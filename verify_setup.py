#!/usr/bin/env python3
"""Verify project setup and dependencies."""

import sys
from pathlib import Path

def check_directories():
    """Check all required directories exist."""
    required_dirs = [
        "agents", "tools", "models", "pipelines", "config",
        "tests", "logs", "artifacts", ".kilocode/rules/memory-bank"
    ]
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            print(f"❌ Missing directory: {dir_path}")
            return False
    print("✅ All directories present")
    return True

def check_dependencies():
    """Check critical dependencies are installed."""
    required_packages = [
        "agno", "crawl4ai", "firecrawl", "llama_cpp",
        "pydantic", "httpx", "typer", "pytest"
    ]
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        return False
    print("✅ All dependencies installed")
    return True

def check_config_files():
    """Check essential config files exist."""
    required_files = [
        ".env.template", "config/settings.yaml",
        "AGENTS.md", "requirements.txt"
    ]
    for file_path in required_files:
        if not Path(file_path).exists():
            print(f"❌ Missing file: {file_path}")
            return False
    print("✅ All config files present")
    return True

if __name__ == "__main__":
    print("🔍 Verifying project setup...\n")
    
    checks = [
        check_directories(),
        check_dependencies(),
        check_config_files()
    ]
    
    if all(checks):
        print("\n🎉 Setup verified successfully!")
        sys.exit(0)
    else:
        print("\n⚠️  Setup incomplete. Review errors above.")
        sys.exit(1)
