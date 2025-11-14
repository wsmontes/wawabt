#!/bin/bash
# Install dependencies for FinBERT sentiment analysis

echo "Installing FinBERT dependencies..."
echo ""

# Check if in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Not in a virtual environment"
    echo "   Activate with: source venv/bin/activate"
    echo ""
fi

# Install PyTorch (CPU version - lighter)
echo "📦 Installing PyTorch (CPU)..."
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install Transformers
echo "📦 Installing Transformers..."
pip install transformers

# Install additional dependencies
echo "📦 Installing additional dependencies..."
pip install sentencepiece
pip install protobuf

echo ""
echo "✅ Installation complete!"
echo ""
echo "To use GPU acceleration (if available), run:"
echo "   pip install torch torchvision torchaudio"
echo ""
echo "Test the installation with:"
echo "   python engines/finbert.py --text 'Stock prices surged today on positive earnings'"
