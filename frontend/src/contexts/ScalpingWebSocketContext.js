import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import config from '../config';

const ScalpingWebSocketContext = createContext(null);

export const ScalpingWebSocketProvider = ({ children }) => {
  const [ws, setWs] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [signals, setSignals] = useState([]);
  const [summary, setSummary] = useState({});
  const [lastMessage, setLastMessage] = useState(null);
  const [connectionError, setConnectionError] = useState(null);
  
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000;

  const connect = useCallback(() => {
    try {
      // Don't create new connection if one already exists
      if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
        return;
      }

      console.log('🚀 Connecting to scalping WebSocket...');
      
      // Create WebSocket URL with API key
      const apiKey = config.API_KEY || 'temp_key_for_development';
      const wsUrl = `${config.WS_BASE_URL}/ws/scalping?api_key=${apiKey}`;
      const newWs = new WebSocket(wsUrl);

      newWs.onopen = () => {
        console.log('✅ Scalping WebSocket connected');
        setIsConnected(true);
        setConnectionError(null);
        reconnectAttempts.current = 0;
      };

      newWs.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
          
          // Handle different message types
          if (data.type === 'scalping_signal_event') {
            handleSignalEvent(data);
          } else if (data.data && data.data.scalping_signals) {
            // Regular data update
            setSignals(data.data.scalping_signals || []);
            setSummary(data.data.scalping_summary || {});
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      newWs.onclose = (event) => {
        console.log('🔌 Scalping WebSocket disconnected', event.code, event.reason);
        setIsConnected(false);
        setWs(null);
        
        // Attempt to reconnect if not closed intentionally
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          scheduleReconnect();
        }
      };

      newWs.onerror = (error) => {
        console.error('❌ Scalping WebSocket error:', error);
        setConnectionError('WebSocket connection failed');
        setIsConnected(false);
      };

      setWs(newWs);
    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
      setConnectionError('Failed to create WebSocket connection');
    }
  }, [ws]);

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    reconnectAttempts.current += 1;
    console.log(`⏰ Scheduling reconnect attempt ${reconnectAttempts.current}/${maxReconnectAttempts} in ${reconnectDelay/1000}s`);
    
    reconnectTimeoutRef.current = setTimeout(() => {
      connect();
    }, reconnectDelay);
  }, [connect]);

  const handleSignalEvent = useCallback((eventData) => {
    const { event_type, signal_id, signal_data, reason } = eventData;
    
    console.log(`📡 Signal event: ${event_type} for ${signal_data?.symbol}`, reason);
    
    setSignals(prevSignals => {
      let updatedSignals = [...prevSignals];
      
      switch (event_type) {
        case 'signal_new':
          // Add new signal if not already exists
          if (!updatedSignals.find(s => s.signal_id === signal_id)) {
            updatedSignals.unshift(signal_data); // Add to beginning
            console.log(`✨ New signal added: ${signal_data.symbol} ${signal_data.direction}`);
          }
          break;
          
        case 'signal_update':
          // Update existing signal
          const updateIndex = updatedSignals.findIndex(s => s.signal_id === signal_id);
          if (updateIndex !== -1) {
            updatedSignals[updateIndex] = { ...updatedSignals[updateIndex], ...signal_data };
            console.log(`🔄 Signal updated: ${signal_data.symbol}`);
          }
          break;
          
        case 'signal_stale':
          // Mark signal as stale
          const staleIndex = updatedSignals.findIndex(s => s.signal_id === signal_id);
          if (staleIndex !== -1) {
            updatedSignals[staleIndex] = { ...updatedSignals[staleIndex], ...signal_data, status: 'stale' };
            console.log(`⚠️ Signal marked stale: ${signal_data.symbol}`);
          }
          break;
          
        case 'signal_invalidate':
          // Remove invalidated signal
          updatedSignals = updatedSignals.filter(s => s.signal_id !== signal_id);
          console.log(`❌ Signal removed: ${signal_data.symbol} - ${reason}`);
          break;
          
        default:
          console.log(`Unknown signal event type: ${event_type}`);
      }
      
      // Sort by timestamp (newest first)
      return updatedSignals.sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
    });
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (ws) {
      ws.close(1000, 'User disconnected');
      setWs(null);
    }
    
    setIsConnected(false);
    reconnectAttempts.current = 0;
  }, [ws]);

  const forceRefresh = useCallback(async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/trading/refresh-scalping`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      const result = await response.json();
      
      if (result.status === 'success') {
        console.log('🔄 Forced scalping refresh completed');
        // Signals will be updated via WebSocket
      } else {
        throw new Error(result.message || 'Refresh failed');
      }
    } catch (error) {
      console.error('Error forcing refresh:', error);
      throw error;
    }
  }, []);

  // Connect on mount
  useEffect(() => {
    connect();
    
    // Cleanup on unmount
    return () => {
      disconnect();
    };
  }, []);

  // Auto-reconnect when connection is lost
  useEffect(() => {
    if (!isConnected && !connectionError && reconnectAttempts.current < maxReconnectAttempts) {
      const timeout = setTimeout(() => {
        if (!isConnected) {
          connect();
        }
      }, 5000);
      
      return () => clearTimeout(timeout);
    }
  }, [isConnected, connectionError, connect]);

  const value = {
    ws,
    isConnected,
    signals,
    summary,
    lastMessage,
    connectionError,
    reconnectAttempts: reconnectAttempts.current,
    maxReconnectAttempts,
    connect,
    disconnect,
    forceRefresh
  };

  return (
    <ScalpingWebSocketContext.Provider value={value}>
      {children}
    </ScalpingWebSocketContext.Provider>
  );
};

export const useScalpingWebSocket = () => {
  const context = useContext(ScalpingWebSocketContext);
  if (!context) {
    throw new Error('useScalpingWebSocket must be used within a ScalpingWebSocketProvider');
  }
  return context;
}; 