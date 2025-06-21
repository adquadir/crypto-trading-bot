const webpack = require('webpack');

module.exports = function override(config, env) {
  // Add webpack 5 polyfills for Node.js modules
  config.resolve.fallback = {
    ...config.resolve.fallback,
    "http": require.resolve("stream-http"),
    "https": require.resolve("https-browserify"),
    "stream": require.resolve("stream-browserify"),
    "util": require.resolve("util/"),
    "zlib": require.resolve("browserify-zlib"),
    "crypto": require.resolve("crypto-browserify"),
    "url": require.resolve("url/"),
    "assert": require.resolve("assert/"),
    "buffer": require.resolve("buffer/"),
    "path": require.resolve("path-browserify"),
    "fs": false,
    "net": false,
    "tls": false,
    "child_process": false
  };

  // Add plugins for global polyfills
  config.plugins = [
    ...config.plugins,
    new webpack.ProvidePlugin({
      process: 'process/browser',
      Buffer: ['buffer', 'Buffer'],
    }),
  ];

  // Update webpack-dev-server configuration
  if (env === 'development') {
    config.devServer = {
      ...config.devServer,
      setupMiddlewares: (middlewares, devServer) => {
        if (!devServer) {
          throw new Error('webpack-dev-server is not defined');
        }
        return middlewares;
      }
    };
  }

  return config;
}; 