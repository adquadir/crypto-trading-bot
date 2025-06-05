import React from 'react';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import App from '../App';

// Mock the child components to simplify testing
jest.mock('../pages/Dashboard', () => () => <div data-testid="dashboard">Dashboard</div>);
jest.mock('../pages/Opportunities', () => () => <div data-testid="opportunities">Opportunities</div>);
jest.mock('../pages/Signals', () => () => <div data-testid="signals">Signals</div>);
jest.mock('../pages/Positions', () => () => <div data-testid="positions">Positions</div>);
jest.mock('../pages/Strategies', () => () => <div data-testid="strategies">Strategies</div>);
jest.mock('../pages/Settings', () => () => <div data-testid="settings">Settings</div>);
jest.mock('../layouts/DashboardLayout', () => ({ children }) => <div data-testid="layout">{children}</div>);

describe('App Component', () => {
  const renderWithRouter = (ui, { route = '/' } = {}) => {
    window.history.pushState({}, 'Test page', route);
    return render(ui, { wrapper: BrowserRouter });
  };

  test('renders dashboard on root path', () => {
    renderWithRouter(<App />);
    expect(screen.getByTestId('dashboard')).toBeInTheDocument();
  });

  test('renders opportunities page', () => {
    renderWithRouter(<App />, { route: '/opportunities' });
    expect(screen.getByTestId('opportunities')).toBeInTheDocument();
  });

  test('renders signals page', () => {
    renderWithRouter(<App />, { route: '/signals' });
    expect(screen.getByTestId('signals')).toBeInTheDocument();
  });

  test('renders positions page', () => {
    renderWithRouter(<App />, { route: '/positions' });
    expect(screen.getByTestId('positions')).toBeInTheDocument();
  });

  test('renders strategies page', () => {
    renderWithRouter(<App />, { route: '/strategies' });
    expect(screen.getByTestId('strategies')).toBeInTheDocument();
  });

  test('renders settings page', () => {
    renderWithRouter(<App />, { route: '/settings' });
    expect(screen.getByTestId('settings')).toBeInTheDocument();
  });

  test('renders layout wrapper', () => {
    renderWithRouter(<App />);
    expect(screen.getByTestId('layout')).toBeInTheDocument();
  });
}); 