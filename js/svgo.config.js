module.exports = {
  multipass: true,
  plugins: [
    { name: 'preset-default' },
    { name: 'removeDimensions', active: true },
    { name: 'removeViewBox', active: false }
  ]
};