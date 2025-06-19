export const obsCoreColumnConfig = {
  obs_id: { displayName: 'Obs. Id', unit: null },
  obs_publisher_did: { displayName: 'Pub. DID', unit: null },
  obs_creator_did: { displayName: 'Creator DID', unit: null },
  obs_title: { displayName: 'Title', unit: null },
  dataproduct_type: { displayName: 'Product type', unit: null },
  dataproduct_subtype: { displayName: 'Subtype', unit: null },
  calib_level: { displayName: 'Calibration level', unit: null },
  target_name: { displayName: 'Target Name', unit: null },
  target_class: { displayName: 'Target Class', unit: null },
  object: { displayName: 'Object', unit: null },
  s_ra: { displayName: 'RA', unit: 'deg' },
  s_dec: { displayName: 'Dec', unit: 'deg' },
  s_fov: { displayName: 'FoV', unit: 'deg' },
  s_region: { displayName: 'Coverage', unit: null },
  s_resolution: { displayName: 'Space Res.', unit: 'deg' },

  t_min: { displayName: 'Min. t', unit: 'd' },
  t_max: { displayName: 'T_max', unit: 'd' },
  t_exptime: { displayName: 'Exp. Time', unit: 's' },
  t_resolution: { displayName: 'Res. t', unit: 's' },
  // date_obs: { displayName: 'Date Obs', unit: null },
  // time_obs: { displayName: 'Time Obs', unit: null },

  em_min: { displayName: 'λ_min', unit: 'm' },
  em_max: { displayName: 'λ_max', unit: 'm' },
  em_ucd: { displayName: 'Spect. UCD', unit: null },
  em_res_power: { displayName: 'λ/Δλ', unit: null },
  // em_resolution: { displayName: 'Spectral Resolution', unit: 'm' },
  o_ucd: { displayName: 'Obs. UCD', unit: null },
  pol_states: { displayName: 'Pol. States', unit: null },
  preview: { displayName: 'Preview', unit: null },
  source_table: { displayName: 'Source Table', unit: null },

  facility_name: { displayName: 'Facility', unit: null },
  instrument_name: { displayName: 'Instrument', unit: null },
  s_xel1: { displayName: '|X|', unit: null },
  s_xel2: { displayName: '|Y|', unit: null },
  t_xel: { displayName: '|t|', unit: null },
  em_xel: { displayName: '|λ|', unit: null },
  pol_xel: { displayName: '|Pol|', unit: null },
  s_pixel_scale: { displayName: 'Pix. Scale', unit: 'arcsec' },
  obs_collection: { displayName: 'Collection', unit: null },

  access_url: { displayName: 'Access URL', unit: null },
  access_format: { displayName: 'Media Type', unit: null },
  access_estsize: { displayName: 'Size', unit: 'kbyte' },

  ra_pnt: { displayName: 'RA Pointing', unit: 'deg' },
  dec_pnt: { displayName: 'Dec Pointing', unit: 'deg' },
  glon_pnt: { displayName: 'Gal Lon Pointing', unit: 'deg' },
  glat_pnt: { displayName: 'Gal Lat Pointing', unit: 'deg' },

  // deadc: { displayName: 'Deadtime Corr.', unit: null },
  // muoneff: { displayName: 'Muon Efficiency', unit: null },
  // event_count: { displayName: 'Event Count', unit: null },
  // offset_obj: { displayName: 'Target Offset', unit: 'deg' },
  // safe_energy_lo: { displayName: 'Safe E Min', unit: 'TeV' },
  // safe_energy_hi: { displayName: 'Safe E Max', unit: 'TeV' },

};

// Helper function to get display info
export const getColumnDisplayInfo = (backendName) => {
  return obsCoreColumnConfig[backendName.toLowerCase()] ||
         obsCoreColumnConfig[backendName] ||
         { displayName: backendName, unit: null };
};
