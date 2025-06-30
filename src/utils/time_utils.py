"""
Time utility functions for formatting durations and timestamps
"""

def format_duration(minutes: int) -> str:
    """
    Format duration in minutes to human-readable format
    
    Args:
        minutes: Duration in minutes
        
    Returns:
        Formatted duration string (e.g., "2h 7m", "1d 3h", "45m")
    """
    if minutes < 0:
        return "0m"
    
    if minutes < 60:
        return f"{minutes}m"
    elif minutes < 1440:  # Less than 24 hours
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if remaining_minutes == 0:
            return f"{hours}h"
        else:
            return f"{hours}h {remaining_minutes}m"
    else:  # 24+ hours
        days = minutes // 1440
        remaining_hours = (minutes % 1440) // 60
        remaining_minutes = minutes % 60
        
        parts = [f"{days}d"]
        if remaining_hours > 0:
            parts.append(f"{remaining_hours}h")
        if remaining_minutes > 0:
            parts.append(f"{remaining_minutes}m")
        
        return " ".join(parts)

def format_duration_detailed(minutes: int) -> dict:
    """
    Format duration with both human-readable and exact values
    
    Args:
        minutes: Duration in minutes
        
    Returns:
        Dict with 'formatted', 'minutes', and 'exact' keys
    """
    return {
        'formatted': format_duration(minutes),
        'minutes': minutes,
        'exact': f"{minutes} minutes"
    }
