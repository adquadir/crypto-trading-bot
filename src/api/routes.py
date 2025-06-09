@router.get("/opportunities")
async def get_opportunities():
    """Get current trading opportunities."""
    try:
        # Get opportunities from the opportunity manager
        opportunities = trading_bot.opportunity_manager.get_opportunities()
        return {
            "status": "success",
            "data": opportunities
        }
    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        return {
            "status": "error",
            "message": str(e)
        } 