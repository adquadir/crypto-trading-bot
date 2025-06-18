import React, { createContext, useContext } from 'react';

// COMPLETELY DISABLED WebSocket Context
// This file exists only to prevent import errors
// No WebSocket connections will ever be made

const WebSocketContext = createContext(null);

export const WebSocketProvider = ({ children }) => {
  // Return children without any WebSocket functionality
  return children;
};

export const useWebSocket = () => {
  // Return safe default values - no WebSocket functionality
  return {
    ws: null,
    isConnected: false,
    lastMessage: null,
    reconnect: () => {}
  };
}; 