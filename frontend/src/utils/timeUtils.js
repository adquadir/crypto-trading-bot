/**
 * Format duration in minutes to human-readable format
 * @param {number} minutes - Duration in minutes
 * @returns {string} Formatted duration string (e.g., "2h 7m", "1d 3h", "45m")
 */
export const formatDuration = (minutes) => {
  if (!minutes || minutes < 0) {
    return "0m";
  }
  
  if (minutes < 60) {
    return `${Math.floor(minutes)}m`;
  } else if (minutes < 1440) { // Less than 24 hours
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = Math.floor(minutes % 60);
    if (remainingMinutes === 0) {
      return `${hours}h`;
    } else {
      return `${hours}h ${remainingMinutes}m`;
    }
  } else { // 24+ hours
    const days = Math.floor(minutes / 1440);
    const remainingHours = Math.floor((minutes % 1440) / 60);
    const remainingMinutes = Math.floor(minutes % 60);
    
    const parts = [`${days}d`];
    if (remainingHours > 0) {
      parts.push(`${remainingHours}h`);
    }
    if (remainingMinutes > 0) {
      parts.push(`${remainingMinutes}m`);
    }
    
    return parts.join(" ");
  }
};

/**
 * Format duration with both human-readable and exact values
 * @param {number} minutes - Duration in minutes
 * @returns {object} Object with 'formatted', 'minutes', and 'exact' keys
 */
export const formatDurationDetailed = (minutes) => {
  return {
    formatted: formatDuration(minutes),
    minutes: minutes,
    exact: `${minutes} minutes`
  };
};
