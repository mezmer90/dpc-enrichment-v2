# Contributing to DPC Enrichment V2

Thank you for considering contributing to DPC Enrichment V2! This document provides guidelines for contributing to the project.

## 🚀 Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/dpc-enrichment-v2.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Test your changes
6. Commit: `git commit -am 'Add some feature'`
7. Push: `git push origin feature/your-feature-name`
8. Create a Pull Request

## 📋 Development Setup

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements_enrichment.txt
playwright install chromium

# Create .env from template
copy .env.example .env
# Add your API keys

# Validate setup
python validate_setup.py
```

## 🧪 Testing

Before submitting a PR:

```bash
# Run validation
python validate_setup.py

# Test with small batch
python batch_enrich_v2.py --limit 5

# Check for Python errors
python -m py_compile src/enrichment_v2/*.py
```

## 📝 Code Style

- Follow PEP 8 guidelines
- Use type hints where possible
- Add docstrings to functions and classes
- Keep functions focused and small
- Use meaningful variable names

## 🔒 Security

- **NEVER** commit API keys or secrets
- Always use environment variables for sensitive data
- Check that `.gitignore` is properly configured
- Review changes before committing

## 🐛 Bug Reports

When reporting bugs, please include:

1. Description of the issue
2. Steps to reproduce
3. Expected behavior
4. Actual behavior
5. Environment (Python version, OS, etc.)
6. Relevant log output from `batch_enrichment_v2.log`

## 💡 Feature Requests

For feature requests:

1. Explain the use case
2. Describe the proposed solution
3. Consider backwards compatibility
4. Estimate impact on performance/cost

## 📦 Pull Request Process

1. Update README.md if needed
2. Update documentation for new features
3. Ensure code follows style guidelines
4. Test thoroughly
5. Update CHANGELOG if applicable
6. Request review from maintainers

## ⚠️ Important Guidelines

- **Test API calls**: Be mindful of API costs when testing
- **Progress tracking**: Don't break auto-save/resume functionality
- **Windows compatibility**: Test on Windows PowerShell
- **API budget protection**: Preserve pause/resume on API failures

## 🤝 Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Help others learn and grow
- Focus on what's best for the project

## 📞 Questions?

- Open an issue for discussion
- Check existing issues first
- Be clear and concise

Thank you for contributing! 🎉
