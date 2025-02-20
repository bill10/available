from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import os
import asyncio
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

def parse_calendly_url(url):
    parts = url.strip('/').split('calendly.com/')
    if len(parts) != 2:
        return None
    return parts[1]

async def get_available_times_async(calendly_link, start_date, end_date):
    try:
        print(f"Getting availability for {calendly_link} from {start_date} to {end_date}")
        
        # Parse Calendly URL
        event_path = parse_calendly_url(calendly_link)
        if not event_path:
            return []  # Return empty list instead of error dict
        
        parts = event_path.split('/')
        if len(parts) != 2:
            return []  # Return empty list for invalid format
            
        organization, event_type_slug = parts
        print(f"Organization: {organization}, Event type: {event_type_slug}")
        
        async with async_playwright() as p:
            # Launch browser with specific viewport size
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={'width': 1280, 'height': 800})
            page = await context.new_page()
            
            try:
                # Get all dates between start and end date
                available_times = []
                duration = None
                current_date = start_date
                
                while current_date <= end_date:
                    # Construct URL for this specific date
                    month_url = f"https://calendly.com/{organization}/{event_type_slug}?month={current_date.strftime('%Y-%m')}&timezone=America/Los_Angeles"
                    print(f"Loading calendar for month: {month_url}")
                    
                    # Load the page and wait for network to be idle
                    response = await page.goto(month_url, wait_until='networkidle')
                    if not response.ok:
                        print(f"Failed to load page: {response.status} {response.status_text}")
                        return {"error": "Failed to load Calendly page", "details": f"Status: {response.status}"}
                    
                    # Wait for page to be fully loaded
                    await page.wait_for_load_state('domcontentloaded')
                    await page.wait_for_load_state('networkidle')
                    
                    # Take screenshot for debugging
                    # await page.screenshot(path=f'calendly_debug_{current_date.strftime("%Y%m%d")}.png')
                    
                    # Check if we're on a valid Calendly page
                    content = await page.content()
                    if 'calendly' not in content.lower():
                        print("Page doesn't appear to be a valid Calendly page")
                        return {"error": "Invalid Calendly page", "details": "Page content doesn't match expected Calendly format"}
                    
                    # Try to find and click the date
                    try:
                        # Handle the privacy consent popup
                        # Wait for the page to load
                        await page.wait_for_load_state('domcontentloaded')
                        await page.wait_for_timeout(2000)
                            
                        # Enhanced privacy popup detection and handling
                        print("Checking for privacy popups...")
                        await page.wait_for_load_state('networkidle')
                        
                        # Debug: Screenshot disabled
                        # await page.screenshot(path='before_privacy.png')
                            
                        # Comprehensive popup detection
                        popup_info = await page.evaluate("""
                            () => {
                                const selectors = [
                                    '#onetrust-banner-sdk',
                                    '#onetrust-consent-sdk',
                                    'div[role="dialog"]',
                                    '[aria-label*="cookie"]',
                                    '[aria-label*="privacy"]',
                                    '.privacy-notice',
                                    '.cookie-banner',
                                    '[class*="cookie"]',
                                    '[class*="privacy"]'
                                ];
                                
                                const popups = selectors
                                    .map(s => document.querySelector(s))
                                    .filter(el => el && window.getComputedStyle(el).display !== 'none');
                                
                                const buttons = Array.from(document.querySelectorAll('button'));
                                const acceptButtons = buttons.filter(b => {
                                    const text = b.textContent.toLowerCase().trim();
                                    return text.includes('accept') || 
                                            text.includes('agree') || 
                                            text.includes('allow') || 
                                            text.includes('understand') || 
                                            text.includes('got it');
                                });
                                
                                return {
                                    popupVisible: popups.length > 0,
                                    popupCount: popups.length,
                                    acceptButtons: acceptButtons.map(b => ({
                                        text: b.textContent.trim(),
                                        id: b.id,
                                        classes: b.className,
                                        visible: window.getComputedStyle(b).display !== 'none'
                                    }))
                                };
                            }
                        """)
                            
                        # Debug: print(f"Popup detection results: {json.dumps(popup_info, indent=2)}")
                        
                        if popup_info.get('popupVisible'):
                            # Debug: print(f"Found {popup_info['popupCount']} privacy popup(s)")
                            
                            # Prioritized list of button selectors to try
                            button_selectors = [
                                '#onetrust-accept-btn-handler',
                                '[aria-label="Accept"]',
                                'button:has-text("Accept")',
                                'button:has-text("I understand")',
                                'button:has-text("Allow")',
                                'button:has-text("Got it")',
                                'button:has-text("Agree")',
                                '[aria-label*="accept"]',
                                '[aria-label*="cookie"]'
                            ]
                                
                            # Try each selector with proper error handling
                            for selector in button_selectors:
                                try:
                                    # print(f"Trying to click button with selector: {selector}")
                                    # First check if the element exists and is visible
                                    button_visible = await page.evaluate(f"""
                                        () => {{
                                            const el = document.querySelector('{selector}');
                                            return el && window.getComputedStyle(el).display !== 'none';
                                        }}
                                    """)
                                    
                                    if button_visible:
                                        await page.click(selector, timeout=2000)
                                        print(f"Successfully clicked {selector}")
                                        # Wait a moment for the click to take effect
                                        await page.wait_for_timeout(1000)
                                        break
                                except Exception as e:
                                    print(f"Failed to click {selector}: {str(e)}")
                                    continue
                                
                            # Take screenshot after privacy handling
                            # await page.screenshot(path='after_privacy.png')

                        # Save the HTML for debugging
                        # html_content = await page.content()
                        # with open('calendar_page.html', 'w', encoding='utf-8') as f:
                        #     f.write(html_content)
                            
                        # Take screenshot of calendar state
                        # await page.screenshot(path='calendar_state.png')

                        # Extract duration if we haven't yet
                        if duration is None:
                            duration_result = await page.evaluate("""
                                () => {
                                    // Find the clock icon by its SVG path
                                    const svgs = Array.from(document.querySelectorAll('svg'));
                                    for (const svg of svgs) {
                                        // Check if this SVG has the clock path
                                        const hasClockPaths = Array.from(svg.querySelectorAll('path')).some(path => 
                                            path.getAttribute('d').includes('M.5 5a4.5 4.5')
                                        );
                                        
                                        if (hasClockPaths) {
                                            // Get the container with the duration text
                                            const container = svg.closest('div');
                                            if (!container) continue;
                                            
                                            const parentDiv = container.parentElement;
                                            const text = parentDiv ? parentDiv.textContent.trim() : container.textContent.trim();
                                            
                                            const match = text.match(/(\d+)\s*(min|minute|hour)/i);
                                            if (match) {
                                                const value = parseInt(match[1]);
                                                return {
                                                    value: value,
                                                    unit: 'minutes'
                                                };
                                            }
                                        }
                                    }
                                    return null;
                                }
                            """)
                            if duration_result:
                                duration = duration_result
                                print(f"Found duration: {duration}")
                            else:
                                print("Duration not found")
                        
                        # Get available dates and find next available
                        calendar_result = await page.evaluate('''
                            (() => {
                                // Find all buttons with "Times available" in their aria-label
                                const allButtons = document.querySelectorAll('button[aria-label*="Times available"]');
                                console.log('Found buttons:', allButtons.length);
                                
                                // Convert NodeList to Array and filter for date buttons
                                const dateButtons = Array.from(allButtons).filter(button => {
                                    const text = button.textContent.trim();
                                    return /^\d+$/.test(text); // Check if text is a number
                                });
                                
                                // Log button details for debugging
                                console.log('Date buttons found:', dateButtons.length);
                                console.log('Button details:', dateButtons.map(button => ({
                                    text: button.textContent.trim(),
                                    ariaLabel: button.getAttribute('aria-label')
                                })));
                                
                                // Extract and sort available dates
                                const availableDates = dateButtons
                                    .map(button => parseInt(button.textContent.trim()))
                                    .sort((a, b) => a - b);
                                
                                console.log('Available dates:', availableDates);
                                
                                return {
                                    availableDates,
                                    buttons: dateButtons.map(button => ({
                                        text: button.textContent.trim(),
                                        ariaLabel: button.getAttribute('aria-label')
                                    }))
                                };
                            })()
                        ''')
                        
                        # print(f"Calendar result: {calendar_result}")
                        
                        if not calendar_result or 'availableDates' not in calendar_result or not calendar_result['availableDates']:
                            print(f"No available dates found for {current_date.strftime('%Y-%m')}")
                            # Move to first day of next month
                            if current_date.month == 12:
                                current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
                            else:
                                current_date = current_date.replace(month=current_date.month + 1, day=1)
                            continue
                        # Get all available dates for the current month
                        available_days = sorted(calendar_result['availableDates'])
                        print(f"Available days in {current_date.strftime('%Y-%m')}: {available_days}")
                        
                        if not available_days:
                            print(f"No available dates found for {current_date.strftime('%Y-%m')}")
                            # Move to first day of next month
                            if current_date.month == 12:
                                current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
                            else:
                                current_date = current_date.replace(month=current_date.month + 1, day=1)
                            continue
                        
                        # Find all days in this month that are within our date range
                        valid_days = []
                        for day in available_days:
                            test_date = current_date.replace(day=day)
                            if start_date <= test_date <= end_date:
                                valid_days.append(day)
                        
                        print(f"Valid days between {start_date} and {end_date}: {valid_days}")
                        
                        if not valid_days:
                            # No valid days in this month, move to next month
                            if current_date.month == 12:
                                current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
                            else:
                                current_date = current_date.replace(month=current_date.month + 1, day=1)
                            continue
                        
                        # Update current_date to the first valid day
                        current_date = current_date.replace(day=valid_days[0])
                        print(f"Starting with date: {current_date.strftime('%Y-%m-%d')}")
                        
                        # Process each valid day in the current month
                        for day in valid_days:
                            try:
                                # Update current date
                                current_date = current_date.replace(day=day)
                                print(f"Processing date: {current_date.strftime('%Y-%m-%d')}")
                                
                                # Click the date
                                click_success = await page.evaluate("""
                                    (targetDay) => {
                                        const buttons = Array.from(document.querySelectorAll('button[aria-label*="Times available"]'));
                                        const targetButton = buttons.find(b => 
                                            b.textContent.trim() === targetDay
                                        );
                                        if (targetButton) {
                                            targetButton.click();
                                            return true;
                                        }
                                        return false;
                                    }
                                """, str(day))
                                
                                if not click_success:
                                    print(f"Failed to click date {current_date.strftime('%Y-%m-%d')}")
                                    continue
                                    
                                print(f"Successfully clicked date {current_date.strftime('%Y-%m-%d')}")
                                
                                # Take screenshot after clicking
                                # await page.screenshot(path=f'after_date_click_{day}.png')
                                
                                # Wait for any updates after clicking
                                await page.wait_for_timeout(2000)
                                await page.wait_for_load_state('networkidle')
        
                                print("Starting time slot detection...")
                                
                                try:
                                    # Get time slots
                                    time_slots = await page.evaluate("""
                                        () => {
                                            // Look for all buttons that might be time slots
                                            const timeButtons = Array.from(document.querySelectorAll('button'));
                                            console.log('Found ' + timeButtons.length + ' total buttons');
                                            
                                            const slots = [];
                                            timeButtons.forEach(button => {
                                                const timeText = button.textContent.trim();
                                                if (!timeText) return;
                                                
                                                // Time format validation - looking for patterns like "6:00am", "7:30am", etc.
                                                const timePattern = /^\d{1,2}:\d{2}(am|pm)$/i;
                                                if (timePattern.test(timeText.toLowerCase())) {
                                                    console.log('Found time slot:', timeText);
                                                    
                                                    // Check if the button or its parent is disabled
                                                    const isDisabled = (
                                                        button.hasAttribute('disabled') || 
                                                        button.getAttribute('aria-disabled') === 'true' ||
                                                        button.closest('[aria-disabled="true"]')
                                                    );
                                                    
                                                    if (!isDisabled) {
                                                        slots.push({
                                                            time: timeText
                                                        });
                                                    }
                                                }
                                            });
                                            
                                            console.log('Found time slots:', slots);
                                            return slots;
                                        }
                                    """)
                                    
                                    print(f"JavaScript evaluation complete. Found {len(time_slots) if time_slots else 0} time slots")
                                    
                                    if not time_slots:
                                        print("No time slots found")
                                        current_date += timedelta(days=1)
                                        continue
                                        
                                    # Debug: Page state save disabled
                                    # await page.screenshot(path='time_slots.png')
                                    # with open('time_slots.html', 'w') as f:
                                    #     f.write(await page.content())
                                        
                                    # Process the time slots
                                    for slot in time_slots:
                                        try:
                                            if not isinstance(slot, dict):
                                                # Debug: print(f"Invalid slot format, expected dict but got {type(slot)}: {slot}")
                                                continue
                                                
                                            if 'time' not in slot:
                                                # Debug: print(f"No time in slot: {slot}")
                                                continue
                                                
                                            time_str = slot['time']
                                            if not time_str:
                                                # Debug: print("Empty time in slot")
                                                continue
                                                
                                            if not isinstance(time_str, str):
                                                # Debug: print(f"Invalid time type, expected str but got {type(time_str)}: {time_str}")
                                                continue
                                                
                                            if not ('am' in time_str.lower() or 'pm' in time_str.lower()):
                                                # Debug: print(f"Invalid time format (no am/pm): {time_str}")
                                                continue
                                                
                                            # Combine date and time
                                            full_time_str = f"{current_date.strftime('%Y-%m-%d')} {time_str}"
                                            # Debug: print(f"Parsing datetime: {full_time_str}")
                                            dt = datetime.strptime(full_time_str, '%Y-%m-%d %I:%M%p')
                                            
                                            # Convert to UTC
                                            utc_offset = timedelta(hours=8)  # Pacific Time is UTC-8
                                            dt = dt + utc_offset
                                            
                                            available_times.append(dt.isoformat() + 'Z')
                                            # Debug: print(f"Added time slot: {time_str} -> {dt.isoformat()}Z")
                                        except (ValueError, TypeError, AttributeError) as e:
                                            print(f"Error processing time slot {slot}: {str(e)}")
                                            continue
                                    
                                    # After processing all slots
                                    if not available_times:
                                        # Debug: print("No valid time slots found after processing")
                                        current_date += timedelta(days=1)
                                        continue
                                    
                                    # Successfully processed slots, move to next date
                                    current_date += timedelta(days=1)
                                    
                                except Exception as e:
                                    print(f"Error processing time slots: {str(e)}")
                                    current_date += timedelta(days=1)
                                    continue
                                
                                # Check if we should stop processing
                                if current_date > end_date:
                                    break

                                # Successfully processed this date
                                current_date += timedelta(days=1)

                            except Exception as e:
                                print(f"Error processing date {current_date.strftime('%Y-%m-%d')}: {e}")
                                current_date += timedelta(days=1)
                                continue

                    except Exception as e:
                        print(f"Error in outer block: {str(e)}")
                        current_date += timedelta(days=1)
                        continue

                # After all dates are processed
                # Sort times before returning
                available_times.sort()
                print(f"\nTotal available times found: {len(available_times)}")
                await browser.close()
                return {
                    "available_times": available_times,
                    "duration": duration
                }
                
            except Exception as e:
                print(f"Error in browser session: {str(e)}")
                await browser.close()
                return []

    except Exception as e:
        print(f"Error in main process: {str(e)}")
        return []  # Return empty list on error

def get_available_times(calendly_link, start_date, end_date):
    return asyncio.run(get_available_times_async(calendly_link, start_date, end_date))

@app.route('/')
def index():
    return render_template('index.html')

def find_common_times(availabilities):
    # Extract all available times
    time_sets = [set(avail.get("available_times", [])) for avail in availabilities if not avail.get("error")]
    
    if not time_sets:
        return []
    
    # Find intersection of all time sets
    common_times = time_sets[0]
    for times in time_sets[1:]:
        common_times = common_times.intersection(times)
    
    return sorted(list(common_times))

@app.route('/get_availability', methods=['POST'])
def get_availability():
    try:
        data = request.json
        calendly_links = data.get('calendly_links', [])
        
        if not calendly_links:
            return jsonify({"error": "No Calendly links provided"})
        
        # Parse dates in YYYY-MM-DD format
        start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d')
        end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d')
        
        # Get availability for each calendar
        availabilities = []
        for link in calendly_links:
            times_result = get_available_times(link, start_date, end_date)
            times = times_result.get('available_times', []) if isinstance(times_result, dict) else []
            availabilities.append({
                'calendly_link': link,
                'available_times': times
            })
        
        # Find common available times
        common_times = find_common_times(availabilities)
        
        return jsonify({
            "calendars": availabilities,
            "common_times": common_times
        })
    except ValueError as e:
        return jsonify({"error": f"Invalid date format: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True, port=3002)