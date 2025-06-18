// Okabe & Ito colour-blind safe palette
export const palette = {
  blue:  '#56B4E9',
  orange:'#E69F00',
  green: '#009E73',
  yellow:'#F0E442',
  red:   '#D55E00',
  purple:'#CC79A7',
  grey:  '#999999'
};

// utility that returns rgba with supplied alpha
export const rgba = (hex, alpha) => {
  const bigint = parseInt(hex.slice(1), 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r},${g},${b},${alpha})`;
};
