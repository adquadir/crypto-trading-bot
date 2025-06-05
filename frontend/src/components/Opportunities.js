import React, { useState, useEffect } from 'react';
import { Table, Card, Badge, Progress, Tooltip, Alert } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, InfoCircleOutlined } from '@ant-design/icons';
import config from '../config';

const Opportunities = () => {
    const [opportunities, setOpportunities] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [wsConnected, setWsConnected] = useState(false);
    
    useEffect(() => {
        // Initial fetch
        fetchOpportunities();
        fetchStats();
        
        // Set up WebSocket connection
        const ws = new WebSocket(`${config.WS_BASE_URL}${config.ENDPOINTS.WS_SIGNALS}`);
        
        ws.onopen = () => {
            setWsConnected(true);
            console.log('WebSocket connected');
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'opportunities_update') {
                setOpportunities(data.data.opportunities);
            }
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            setWsConnected(false);
        };
        
        ws.onclose = () => {
            setWsConnected(false);
            console.log('WebSocket disconnected');
        };
        
        return () => {
            ws.close();
        };
    }, []);
    
    const fetchOpportunities = async () => {
        try {
            const response = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.OPPORTUNITIES}`);
            const data = await response.json();
            setOpportunities(data.opportunities);
            setLoading(false);
        } catch (error) {
            setError('Failed to fetch opportunities');
            setLoading(false);
        }
    };
    
    const fetchStats = async () => {
        try {
            const response = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.OPPORTUNITY_STATS}`);
            const data = await response.json();
            setStats(data);
        } catch (error) {
            console.error('Failed to fetch stats:', error);
        }
    };
    
    const columns = [
        {
            title: 'Symbol',
            dataIndex: 'symbol',
            key: 'symbol',
            render: (text) => <strong>{text}</strong>
        },
        {
            title: 'Direction',
            dataIndex: 'direction',
            key: 'direction',
            render: (direction) => (
                <Badge
                    color={direction === 'LONG' ? 'green' : 'red'}
                    text={
                        <span>
                            {direction === 'LONG' ? (
                                <ArrowUpOutlined style={{ color: '#52c41a' }} />
                            ) : (
                                <ArrowDownOutlined style={{ color: '#f5222d' }} />
                            )}
                            {direction}
                        </span>
                    }
                />
            )
        },
        {
            title: 'Entry',
            dataIndex: 'entry_price',
            key: 'entry_price',
            render: (price) => price.toFixed(2)
        },
        {
            title: 'Take Profit',
            dataIndex: 'take_profit',
            key: 'take_profit',
            render: (price) => price.toFixed(2)
        },
        {
            title: 'Stop Loss',
            dataIndex: 'stop_loss',
            key: 'stop_loss',
            render: (price) => price.toFixed(2)
        },
        {
            title: 'Risk/Reward',
            dataIndex: 'risk_reward',
            key: 'risk_reward',
            render: (rr) => rr.toFixed(2)
        },
        {
            title: 'Leverage',
            dataIndex: 'leverage',
            key: 'leverage',
            render: (lev) => `${lev.toFixed(1)}x`
        },
        {
            title: 'Score',
            dataIndex: 'score',
            key: 'score',
            render: (score) => (
                <Tooltip title={`Confidence: ${(score * 100).toFixed(1)}%`}>
                    <Progress
                        percent={score * 100}
                        size="small"
                        status={score > 0.7 ? 'success' : score > 0.4 ? 'normal' : 'exception'}
                    />
                </Tooltip>
            )
        },
        {
            title: 'Volume 24h',
            dataIndex: 'volume_24h',
            key: 'volume_24h',
            render: (volume) => `$${(volume / 1000000).toFixed(1)}M`
        }
    ];
    
    return (
        <div className="opportunities-container">
            <Card
                title="Trading Opportunities"
                extra={
                    <Badge
                        status={wsConnected ? 'success' : 'error'}
                        text={wsConnected ? 'Live Updates' : 'Offline'}
                    />
                }
            >
                {error && (
                    <Alert
                        message="Error"
                        description={error}
                        type="error"
                        showIcon
                        style={{ marginBottom: 16 }}
                    />
                )}
                
                {stats && (
                    <div className="stats-summary" style={{ marginBottom: 16 }}>
                        <Card size="small">
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <div>
                                    <InfoCircleOutlined /> Total Opportunities: {stats.total_opportunities}
                                </div>
                                <div>
                                    Long: {stats.long_opportunities} | Short: {stats.short_opportunities}
                                </div>
                                <div>
                                    Avg Score: {(stats.avg_score * 100).toFixed(1)}%
                                </div>
                            </div>
                        </Card>
                    </div>
                )}
                
                <Table
                    columns={columns}
                    dataSource={opportunities}
                    loading={loading}
                    rowKey="symbol"
                    pagination={false}
                    scroll={{ x: true }}
                />
            </Card>
        </div>
    );
};

export default Opportunities; 