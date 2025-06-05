import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import axios from 'axios';
import Opportunities from '../pages/Opportunities';

// Mock axios
jest.mock('axios');

describe('Opportunities Component', () => {
  const mockOpportunities = [
    {
      symbol: 'BTCUSDT',
      direction: 'LONG',
      entry_price: 50000,
      stop_loss: 49000,
      take_profit: 52000,
      score: 0.85,
      risk_reward: 2.5,
      timestamp: '2024-01-01T00:00:00Z'
    }
  ];

  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();
  });

  test('renders loading state initially', () => {
    render(<Opportunities />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  test('renders opportunities data successfully', async () => {
    axios.get.mockResolvedValueOnce({ data: mockOpportunities });

    render(<Opportunities />);

    // Wait for the data to load
    await waitFor(() => {
      expect(screen.getByText('BTCUSDT')).toBeInTheDocument();
    });

    // Check if all opportunity details are rendered
    expect(screen.getByText('LONG')).toBeInTheDocument();
    expect(screen.getByText('50,000')).toBeInTheDocument();
    expect(screen.getByText('49,000')).toBeInTheDocument();
    expect(screen.getByText('52,000')).toBeInTheDocument();
    expect(screen.getByText('0.85')).toBeInTheDocument();
    expect(screen.getByText('2.50')).toBeInTheDocument();
  });

  test('handles API error gracefully', async () => {
    axios.get.mockRejectedValueOnce(new Error('Failed to fetch'));

    render(<Opportunities />);

    // Wait for error message
    await waitFor(() => {
      expect(screen.getByText(/error loading opportunities/i)).toBeInTheDocument();
    });
  });

  test('refreshes data when refresh button is clicked', async () => {
    axios.get.mockResolvedValueOnce({ data: mockOpportunities });

    render(<Opportunities />);

    // Wait for initial data load
    await waitFor(() => {
      expect(screen.getByText('BTCUSDT')).toBeInTheDocument();
    });

    // Mock new data for refresh
    const newOpportunities = [
      {
        symbol: 'ETHUSDT',
        direction: 'SHORT',
        entry_price: 3000,
        stop_loss: 3100,
        take_profit: 2800,
        score: 0.75,
        risk_reward: 2.0,
        timestamp: '2024-01-01T00:01:00Z'
      }
    ];
    axios.get.mockResolvedValueOnce({ data: newOpportunities });

    // Click refresh button
    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    fireEvent.click(refreshButton);

    // Wait for new data
    await waitFor(() => {
      expect(screen.getByText('ETHUSDT')).toBeInTheDocument();
    });
  });

  test('displays empty state when no opportunities are available', async () => {
    axios.get.mockResolvedValueOnce({ data: [] });

    render(<Opportunities />);

    await waitFor(() => {
      expect(screen.getByText(/no opportunities available/i)).toBeInTheDocument();
    });
  });

  test('handles malformed data gracefully', async () => {
    const malformedData = [
      {
        symbol: 'BTCUSDT',
        // Missing required fields
      }
    ];
    axios.get.mockResolvedValueOnce({ data: malformedData });

    render(<Opportunities />);

    await waitFor(() => {
      expect(screen.getByText(/error processing opportunities/i)).toBeInTheDocument();
    });
  });
}); 