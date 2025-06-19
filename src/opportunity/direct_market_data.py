"""Real-time market data fetcher with multiple sources and proxy support."""

import aiohttp
import asyncio
import logging
from typing import List, Dict, Optional
import random

logger = logging.getLogger(__name__)

class DirectMarketDataFetcher:
    """Fetch real market data from multiple sources with failover."""
    
    def __init__(self):
        # Multiple data sources for redundancy - FUTURES FIRST for trading
        self.data_sources = [
            {
                'name': 'binance_futures', 
                'base_url': 'https://fapi.binance.com',
                'klines_path': '/fapi/v1/klines',
                'ticker_path': '/fapi/v1/ticker/24hr',
                'funding_path': '/fapi/v1/fundingRate',
                'oi_path': '/fapi/v1/openInterest'
            },
            {
                'name': 'binance_futures_testnet', 
                'base_url': 'https://testnet.binancefuture.com',
                'klines_path': '/fapi/v1/klines',
                'ticker_path': '/fapi/v1/ticker/24hr',
                'funding_path': '/fapi/v1/fundingRate',
                'oi_path': '/fapi/v1/openInterest'
            },
            {
                'name': 'binance_spot_backup',
                'base_url': 'https://api.binance.com',
                'klines_path': '/api/v3/klines',
                'ticker_path': '/api/v3/ticker/24hr'
            },
            {
                'name': 'binance_us_backup',
                'base_url': 'https://api.binance.us',
                'klines_path': '/api/v3/klines', 
                'ticker_path': '/api/v3/ticker/24hr'
            }
        ]
        
        # Proxy configuration
        self.proxies = [
            None,  # Direct connection first
            'http://sp6qilmhb3:y2ok7Y3FEygM~rs7de@isp.decodo.com:10001',
            'http://rotating.datacenter.proxy:8080',  # Example backup proxy
        ]
        
    async def get_klines(self, symbol: str, interval: str = '15m', limit: int = 100) -> Optional[List[Dict]]:
        """Get real klines data from multiple sources with failover."""
        
        # Try each data source - FUTURES FIRST
        for source in self.data_sources:
            try:
                # All sources are now Binance-style APIs
                klines = await self._fetch_binance_klines(source, symbol, interval, limit)
                if klines:
                    data_type = "FUTURES" if "futures" in source['name'] else "SPOT"
                    logger.info(f"✓ Real {data_type} market data from {source['name']} for {symbol}: {len(klines)} candles")
                    return klines
                        
            except Exception as e:
                logger.debug(f"Failed to get data from {source['name']}: {e}")
                continue
        
        logger.warning(f"All data sources failed for {symbol} - no real market data available")
        return None
    
    async def _fetch_binance_klines(self, source: Dict, symbol: str, interval: str, limit: int) -> Optional[List[Dict]]:
        """Fetch klines from Binance-style APIs."""
        url = f"{source['base_url']}{source['klines_path']}"
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        # Try with different proxies
        for proxy in self.proxies:
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                connector = aiohttp.TCPConnector(limit=10)
                
                async with aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                ) as session:
                    
                    kwargs = {'params': params}
                    if proxy:
                        kwargs['proxy'] = proxy
                    
                    async with session.get(url, **kwargs) as response:
                        if response.status == 200:
                            data = await response.json()
                            return self._convert_binance_klines(data)
                        elif response.status == 451:
                            logger.debug(f"Geo-blocked from {source['name']} (HTTP 451)")
                            continue
                        else:
                            logger.debug(f"{source['name']} returned HTTP {response.status}")
                            continue
                            
            except Exception as e:
                logger.debug(f"Error with {source['name']} via proxy {proxy}: {e}")
                continue
                
        return None
    

    
    def _convert_binance_klines(self, data: List) -> List[Dict]:
        """Convert Binance klines format to standard format."""
        klines = []
        for candle in data:
            klines.append({
                'openTime': int(candle[0]),
                'open': float(candle[1]),
                'high': float(candle[2]),
                'low': float(candle[3]),
                'close': float(candle[4]),
                'volume': float(candle[5]),
                'closeTime': int(candle[6]),
                'quoteAssetVolume': float(candle[7]),
                'numberOfTrades': int(candle[8]),
                'takerBuyBaseAssetVolume': float(candle[9]),
                'takerBuyQuoteAssetVolume': float(candle[10])
            })
        return klines
    

    
    async def get_ticker_24h(self, symbol: str) -> Optional[Dict]:
        """Get 24h ticker data from multiple sources."""
        
        # Try Binance sources first
        for source in self.data_sources[:3]:  # Skip Coinbase for ticker
            try:
                url = f"{source['base_url']}{source['ticker_path']}"
                params = {'symbol': symbol}
                
                for proxy in self.proxies:
                    try:
                        timeout = aiohttp.ClientTimeout(total=5)
                        async with aiohttp.ClientSession(timeout=timeout) as session:
                            kwargs = {'params': params}
                            if proxy:
                                kwargs['proxy'] = proxy
                                
                            async with session.get(url, **kwargs) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    logger.debug(f"✓ Real ticker from {source['name']} for {symbol}")
                                    return data
                                    
                    except Exception:
                        continue
                        
            except Exception:
                continue
                
        return None
    
    async def get_funding_rate(self, symbol: str) -> Optional[Dict]:
        """Get current funding rate for futures symbol."""
        for source in self.data_sources:
            if 'funding_path' not in source:
                continue  # Skip spot sources
                
            try:
                url = f"{source['base_url']}{source['funding_path']}"
                params = {'symbol': symbol, 'limit': 1}
                
                for proxy in self.proxies:
                    try:
                        timeout = aiohttp.ClientTimeout(total=5)
                        async with aiohttp.ClientSession(timeout=timeout) as session:
                            kwargs = {'params': params}
                            if proxy:
                                kwargs['proxy'] = proxy
                                
                            async with session.get(url, **kwargs) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    if data:
                                        logger.debug(f"✓ Funding rate from {source['name']} for {symbol}")
                                        return data[0] if isinstance(data, list) else data
                                        
                    except Exception:
                        continue
                        
            except Exception:
                continue
                
        return None
    
    async def get_open_interest(self, symbol: str) -> Optional[Dict]:
        """Get open interest for futures symbol."""
        for source in self.data_sources:
            if 'oi_path' not in source:
                continue  # Skip spot sources
                
            try:
                url = f"{source['base_url']}{source['oi_path']}"
                params = {'symbol': symbol}
                
                for proxy in self.proxies:
                    try:
                        timeout = aiohttp.ClientTimeout(total=5)
                        async with aiohttp.ClientSession(timeout=timeout) as session:
                            kwargs = {'params': params}
                            if proxy:
                                kwargs['proxy'] = proxy
                                
                            async with session.get(url, **kwargs) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    logger.debug(f"✓ Open interest from {source['name']} for {symbol}")
                                    return data
                                    
                    except Exception:
                        continue
                        
            except Exception:
                continue
                
        return None
    
    async def get_futures_data_complete(self, symbol: str, interval: str = '15m', limit: int = 100) -> Optional[Dict]:
        """Get complete futures data including klines, funding rate, and open interest."""
        try:
            # Get klines (prioritizes futures)
            klines = await self.get_klines(symbol, interval, limit)
            if not klines:
                return None
            
            # Get futures-specific data
            funding_rate = await self.get_funding_rate(symbol)
            open_interest = await self.get_open_interest(symbol)
            
            return {
                'klines': klines,
                'funding_rate': funding_rate,
                'open_interest': open_interest,
                'symbol': symbol,
                'data_type': 'FUTURES'
            }
            
        except Exception as e:
            logger.warning(f"Error getting complete futures data for {symbol}: {e}")
            return None

# Create global instance
direct_fetcher = DirectMarketDataFetcher() 