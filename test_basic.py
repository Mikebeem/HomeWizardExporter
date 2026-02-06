#!/usr/bin/env python3
"""
Basic tests for HomeWizard Exporter
"""

import sys
import os

# Simple smoke tests that don't require dependencies


def test_file_structure():
    """Test that all required files exist"""
    required_files = [
        'app.py',
        'generate_report.py',
        'requirements.txt',
        'Dockerfile',
        'docker-compose.yml',
        'README.md',
        '.env.example',
        '.gitignore'
    ]
    
    for file in required_files:
        assert os.path.exists(file), f"Missing required file: {file}"
    
    print("✓ All required files exist")


def test_python_syntax():
    """Test that Python files have valid syntax"""
    import py_compile
    
    python_files = ['app.py', 'generate_report.py']
    
    for file in python_files:
        try:
            py_compile.compile(file, doraise=True)
            print(f"✓ {file} has valid syntax")
        except py_compile.PyCompileError as e:
            print(f"✗ {file} has syntax errors: {e}")
            raise


def test_requirements():
    """Test that requirements.txt is readable"""
    with open('requirements.txt', 'r') as f:
        requirements = f.read().strip().split('\n')
    
    assert any('requests' in req for req in requirements), "Should include requests"
    assert any('psycopg2' in req for req in requirements), "Should include psycopg2"
    
    print("✓ Requirements file is valid")


def test_docker_files():
    """Test that Docker files have expected content"""
    with open('Dockerfile', 'r') as f:
        dockerfile = f.read()
    
    assert 'FROM python' in dockerfile, "Dockerfile should use Python base image"
    assert 'requirements.txt' in dockerfile, "Dockerfile should install requirements"
    assert 'app.py' in dockerfile, "Dockerfile should copy app.py"
    assert 'generate_report.py' in dockerfile, "Dockerfile should copy generate_report.py"
    
    print("✓ Dockerfile is valid")
    
    with open('docker-compose.yml', 'r') as f:
        compose = f.read()
    
    assert 'postgres' in compose, "docker-compose should include postgres"
    assert 'HOMEWIZARD_HOST' in compose, "docker-compose should have HOMEWIZARD_HOST"
    assert 'DB_PASSWORD' in compose, "docker-compose should have DB_PASSWORD"
    
    print("✓ docker-compose.yml is valid")


if __name__ == '__main__':
    print("Running HomeWizard Exporter tests...\n")
    
    try:
        test_file_structure()
        test_python_syntax()
        test_requirements()
        test_docker_files()
        
        print("\n✅ All tests passed!")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
