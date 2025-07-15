module.exports = {
  apps: [
    {
      name: 'crypto-trading-api',
      script: './venv/bin/python',
      args: '-m src.api.main',  // Use the new main with profit scraping support
      cwd: '/home/ubuntu/crypto-trading-bot',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      error_file: './logs/api-err.log',
      out_file: './logs/api-out.log',
      log_file: './logs/api-combined.log',
      env: {
        PYTHONPATH: '/home/ubuntu/crypto-trading-bot'
      }
    },
    {
      name: 'paper-trading-auto-start',
      script: './venv/bin/python',
      args: 'auto_start_paper_trading.py',
      cwd: '/home/ubuntu/crypto-trading-bot',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '200M',
      error_file: './logs/paper-trading-err.log',
      out_file: './logs/paper-trading-out.log',
      log_file: './logs/paper-trading-combined.log',
      env: {
        PYTHONPATH: '/home/ubuntu/crypto-trading-bot'
      }
    },
    {
      name: 'crypto-trading-frontend',
      script: '/usr/bin/npm',
      args: 'run start',
      cwd: '/home/ubuntu/crypto-trading-bot/frontend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '200M',
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
