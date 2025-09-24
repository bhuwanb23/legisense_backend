# Render Deployment Guide

This guide will help you deploy your Django backend to Render's free plan.

## Prerequisites

1. A GitHub repository with your code
2. A Render account (sign up at render.com)
3. Your OpenRouter API key (if using AI features)

## Deployment Steps

### 1. Push to GitHub
Make sure all your code is committed and pushed to your GitHub repository.

### 2. Connect to Render
1. Go to [render.com](https://render.com) and sign in
2. Click "New +" and select "Web Service"
3. Connect your GitHub repository
4. Select your repository

### 3. Configure Service
Render will automatically detect the `render.yaml` file and configure your service. The configuration includes:

- **Service Type**: Web Service
- **Environment**: Python
- **Plan**: Free
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python manage.py migrate && gunicorn legisense_backend.wsgi:application`

### 4. Environment Variables
Set these environment variables in your Render dashboard:

- `DEBUG`: `false`
- `SECRET_KEY`: (Render will generate this automatically)
- `ALLOWED_HOSTS`: `legisense-backend.onrender.com`
- `OPENROUTER_API_KEY`: Your OpenRouter API key
- `OPENROUTER_MODEL`: `openai/gpt-4o-mini`

### 5. Database
The `render.yaml` configuration automatically creates a PostgreSQL database for you.

## Files Created for Deployment

1. **render.yaml**: Render configuration file
2. **build.sh**: Build script for deployment
3. **Updated settings.py**: Production-ready Django settings

## Important Notes

- The free plan has limitations (sleeps after 15 minutes of inactivity)
- Static files are served via WhiteNoise
- Database migrations run automatically on deployment
- CORS is configured for production

## Troubleshooting

If you encounter issues:

1. Check the Render logs for error messages
2. Ensure all environment variables are set correctly
3. Verify your OpenRouter API key is valid
4. Check that all dependencies are in requirements.txt

## Local Development

For local development, create a `.env` file with:

```
DEBUG=true
SECRET_KEY=your-local-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1
OPENROUTER_API_KEY=your-api-key
OPENROUTER_MODEL=openai/gpt-4o-mini
```

Then run:
```bash
python manage.py runserver
```
