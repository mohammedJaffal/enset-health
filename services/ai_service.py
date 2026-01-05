"""
AI Service for Health Monitoring Platform

This module provides AI-powered health insights using DeepSeek API.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional, Dict
from services.db_service import get_all_records, get_records_as_dataframe
import pandas as pd

# Load environment variables
load_dotenv()


def get_ai_client() -> Optional[OpenAI]:
    """
    Initialize and return the DeepSeek AI client.
    
    Returns:
        OpenAI: Configured client for DeepSeek API, or None if API key is missing
    """
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        return None
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )
    return client


def get_health_summary_text() -> str:
    """
    Generate a text summary of health data for AI analysis.
    
    Returns:
        str: Formatted text summary of health records
    """
    df = get_records_as_dataframe()
    if df.empty:
        return "No health data available."
    
    # Calculate statistics
    avg_heart_rate = df['Heart_Rate'].mean()
    avg_sleep = df['Sleep_Hours'].mean()
    avg_steps = df['Steps'].mean()
    
    # Count alert days
    high_hr_days = len(df[df['Heart_Rate'] > 110])
    low_sleep_days = len(df[df['Sleep_Hours'] < 5.0])
    
    # Get latest record
    latest = df.iloc[-1]
    
    summary = f"""
Health Data Summary (Last {len(df)} days):

Average Metrics:
- Heart Rate: {avg_heart_rate:.1f} bpm
- Sleep: {avg_sleep:.1f} hours per night
- Steps: {avg_steps:.0f} steps per day

Alert Days:
- High Heart Rate (>110 bpm): {high_hr_days} days
- Low Sleep (<5 hours): {low_sleep_days} days

Latest Record ({latest['Date'].strftime('%Y-%m-%d')}):
- Heart Rate: {latest['Heart_Rate']} bpm
- Sleep: {latest['Sleep_Hours']} hours
- Steps: {latest['Steps']} steps
"""
    return summary


def get_ai_insights(prompt: Optional[str] = None, summary_override: Optional[str] = None) -> Dict:
    """
    Get AI-powered health insights from DeepSeek.
    
    Args:
        prompt: Optional custom prompt. If None, uses default health analysis prompt.
    
    Returns:
        dict: Dictionary with 'success', 'response', and 'error' keys
    """
    def _truncate(value: Optional[str], limit: int = 500) -> Optional[str]:
        if value is None:
            return None
        text = str(value)
        return text if len(text) <= limit else text[:limit] + '...'

    model_name = "deepseek-chat"
    key_present = bool(os.getenv('DEEPSEEK_API_KEY'))
    client = get_ai_client()
    print(f"AI debug: client={'yes' if client else 'no'} key_present={key_present} model={model_name}")
    if client is None:
        return {
            'success': False,
            'response': None,
            'error': 'AI is not configured on this server.',
            'error_type': 'missing_api_key'
        }
    
    # Prepare health data summary
    health_summary = summary_override if summary_override else get_health_summary_text()
    
    # Default prompt if none provided
    if prompt is None:
        prompt = """You are a health monitoring AI assistant. Analyze the following health data and provide:
1. Overall health assessment
2. Key trends and patterns
3. Specific recommendations for improvement
4. Any concerns that should be addressed

Be concise, professional, and actionable in your response."""
    
    full_prompt = f"{prompt}\n\n{health_summary}"
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a helpful health monitoring AI assistant. Provide clear, actionable health insights."},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        ai_response = response.choices[0].message.content
        
        return {
            'success': True,
            'response': ai_response,
            'error': None,
            'error_type': None
        }
    except Exception as exc:
        exc_name = type(exc).__name__
        message = str(exc)
        status = None
        body = None
        response = getattr(exc, 'response', None)
        if response is not None:
            status = getattr(response, 'status_code', None)
            body = getattr(response, 'text', None) or getattr(response, 'content', None)
        if body is None:
            body = getattr(exc, 'body', None)
        body = _truncate(body)
        print(f"AI error: type={exc_name} message={message} status={status} body={body}")

        lowered = message.lower()
        if 'rate' in lowered and 'limit' in lowered or status == 429 or 'ratelimit' in exc_name.lower():
            error_type = 'rate_limited'
        elif 'timeout' in lowered or 'timed out' in lowered or 'timeout' in exc_name.lower():
            error_type = 'timeout'
        elif 'auth' in exc_name.lower() or status == 401:
            error_type = 'auth'
        else:
            error_type = 'unknown'

        return {
            'success': False,
            'response': None,
            'error': f"Error calling AI service: {message}",
            'error_type': error_type
        }


def get_ai_recommendation_for_metric(metric_name: str, value: float) -> Dict:
    """
    Get AI recommendation for a specific health metric.
    
    Args:
        metric_name: Name of the metric (e.g., 'heart_rate', 'sleep_hours')
        value: Current value of the metric
    
    Returns:
        dict: Dictionary with AI recommendation
    """
    client = get_ai_client()
    if client is None:
        return {
            'success': False,
            'response': None,
            'error': 'DEEPSEEK_API_KEY not found in environment variables.'
        }
    
    prompts = {
        'heart_rate': f"My average heart rate is {value:.1f} bpm. Is this normal? What should I do?",
        'sleep_hours': f"I'm getting {value:.1f} hours of sleep per night on average. Is this enough? What are your recommendations?",
        'steps': f"I'm averaging {value:.0f} steps per day. Is this a good activity level?"
    }
    
    prompt = prompts.get(metric_name.lower(), f"My {metric_name} is {value}. What are your recommendations?")
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a health monitoring AI assistant. Provide concise, actionable advice."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        ai_response = response.choices[0].message.content
        
        return {
            'success': True,
            'response': ai_response,
            'error': None
        }
    except Exception as e:
        return {
            'success': False,
            'response': None,
            'error': f"Error calling AI service: {str(e)}"
        }

