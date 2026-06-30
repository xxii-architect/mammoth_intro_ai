Write-Host "Mammoth OS Dev Environment Bootstrap" -ForegroundColor Cyan

# 1. Activate virtual environment
Write-Host "Activating virtual environment..."
.\.venv\Scripts\activate

# 2. Install dependencies
Write-Host "Installing Python dependencies..."
pip install -r requirements.txt

# 3. Verify core modules
Write-Host "Verifying environment..."
python -c "import requests, supabase, dotenv, openai; print('Python environment ready.')"

Write-Host "Mammoth OS environment is ready to run." -ForegroundColor Green
