# Calendly Availability Checker

This is a Flask web application that allows users to check available time slots for a Calendly link within a specified date range.

## Setup

1. Clone the repository
2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

4. Get your Calendly API token:
   - Log in to your Calendly account
   - Go to your [Calendly API & Webhooks settings](https://calendly.com/integrations/api_webhooks)
   - Generate a new API token
   - Add the token to your `.env` file

## Running the Application

1. Start the Flask development server:
```bash
python app.py
```

2. Open your browser and navigate to `http://localhost:5000`

## Usage

1. Enter your Calendly event link
2. Select a date range
3. Click "Check Availability" to see available time slots

## Features

- Simple and intuitive web interface
- Real-time availability checking
- Date range selection
- Responsive design
- Loading indicators
- Error handling

## Requirements

- Python 3.7+
- Flask
- Requests
- python-dotenv
- Flask-WTF
