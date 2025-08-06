module.exports = {
  apps: [
    // 🎯 CONSOLIDATED: Main Trading API with Profit Scraping Engine
    {
      name: 'crypto-trading-api',
      script: './venv/bin/python',
      args: 'lightweight_api.py',
      cwd: '/home/ubuntu/crypto-trading-bot',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '800M',
      restart_delay: 5000,
      max_restarts: 10,
      min_uptime: '30s',
      error_file: './logs/api-err.log',
      out_file: './logs/api-out.log',
      log_file: './logs/api-combined.log',
      env: {
        PYTHONPATH: '/home/ubuntu/crypto-trading-bot',
        PURE_PROFIT_SCRAPING_MODE: 'true',
        PROFIT_SCRAPING_PRIMARY: 'true',
        AUTO_START_PAPER_TRADING: 'true',
        AUTO_START_PROFIT_SCRAPING: 'true'
      }
    },
    // 🎯 Frontend Service
    {
      name: 'crypto-trading-frontend',
      script: '/usr/bin/npm',
      args: 'run start',
      cwd: '/home/ubuntu/crypto-trading-bot/frontend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '200M',
      restart_delay: 10000,
      depends_on: ['crypto-trading-api'],
      error_file: './logs/frontend-err.log',
      out_file: './logs/frontend-out.log',
      env: {
        PORT: 3000,
        BROWSER: 'none',
        CI: 'true'
      }
    }
  ]
};
