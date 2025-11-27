#!/usr/bin/env python3
"""
Setup script for Law Domain Agents

Steps:
1. Create .env file from template
2. Install dependencies
3. Verify Neo4j connection
4. Test OpenAI API key
"""

import os
import sys
from pathlib import Path
import shutil


def create_env_file():
    """Create .env file from .env.example"""
    print("\n" + "="*60)
    print("Step 1: Create .env file")
    print("="*60)

    env_example = Path(".env.example")
    env_file = Path(".env")

    if env_file.exists():
        print(f"✓ .env file already exists")
        overwrite = input("Overwrite? (y/N): ").lower().strip()
        if overwrite != 'y':
            print("Skipping .env creation")
            return True

    if env_example.exists():
        shutil.copy(env_example, env_file)
        print(f"✓ Created .env from .env.example")
        print("\n⚠️  IMPORTANT: Edit .env and set your credentials:")
        print("   - NEO4J_PASSWORD")
        print("   - OPENAI_API_KEY")
        return True
    else:
        print("✗ .env.example not found")
        return False


def install_dependencies():
    """Install Python dependencies"""
    print("\n" + "="*60)
    print("Step 2: Install Dependencies")
    print("="*60)

    requirements_file = Path("requirements.txt")

    if not requirements_file.exists():
        print("✗ requirements.txt not found")
        return False

    print("\nInstalling dependencies...")
    print("Command: pip install -r requirements.txt")
    print("\nNote: Run this manually:")
    print("  pip install -r requirements.txt")
    print("  OR")
    print("  uv pip install -r requirements.txt")

    return True


def verify_neo4j():
    """Verify Neo4j connection"""
    print("\n" + "="*60)
    print("Step 3: Verify Neo4j Connection")
    print("="*60)

    try:
        from dotenv import load_dotenv
        load_dotenv()

        from neo4j import GraphDatabase
        import os

        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "")

        if not password:
            print("⚠️  NEO4J_PASSWORD not set in .env")
            return False

        print(f"Connecting to Neo4j at {uri}...")
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        driver.close()

        print("✓ Neo4j connection successful")
        return True

    except ImportError:
        print("⚠️  neo4j package not installed yet")
        print("   Run: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"✗ Neo4j connection failed: {e}")
        return False


def verify_openai():
    """Verify OpenAI API key"""
    print("\n" + "="*60)
    print("Step 4: Verify OpenAI API Key")
    print("="*60)

    try:
        from dotenv import load_dotenv
        load_dotenv()

        from openai import OpenAI
        import os

        api_key = os.getenv("OPENAI_API_KEY", "")

        if not api_key:
            print("⚠️  OPENAI_API_KEY not set in .env")
            return False

        print("Testing OpenAI API key...")
        client = OpenAI(api_key=api_key)

        # Simple test call
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5
        )

        print("✓ OpenAI API key is valid")
        return True

    except ImportError:
        print("⚠️  openai package not installed yet")
        print("   Run: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"✗ OpenAI API test failed: {e}")
        return False


def main():
    """Run setup"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║ Law Domain Agents - Setup                                    ║
╚══════════════════════════════════════════════════════════════╝

This script will help you set up the project.
""")

    results = []

    # Step 1: Create .env
    results.append(("Create .env file", create_env_file()))

    # Step 2: Install dependencies
    results.append(("Install dependencies", install_dependencies()))

    # Ask if user wants to continue with verification
    print("\n" + "="*60)
    continue_verify = input("\nContinue with connection verification? (y/N): ").lower().strip()

    if continue_verify == 'y':
        # Step 3: Verify Neo4j
        results.append(("Verify Neo4j", verify_neo4j()))

        # Step 4: Verify OpenAI
        results.append(("Verify OpenAI", verify_openai()))

    # Summary
    print("\n" + "="*60)
    print("SETUP SUMMARY")
    print("="*60)

    for name, result in results:
        status = "✓" if result else "✗"
        print(f"{status} {name}")

    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("""
1. Edit .env file with your credentials:
   - NEO4J_PASSWORD
   - OPENAI_API_KEY

2. Install dependencies (if not done):
   pip install -r requirements.txt

3. Run Domain 1 agent:
   python run_domain_1.py

4. Test agent (in another terminal):
   python test_domain_1.py

5. Check API docs:
   http://localhost:8011/docs
""")


if __name__ == "__main__":
    main()
