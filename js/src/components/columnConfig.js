export const obsCoreColumnConfig = {
  obs_id: {
    displayName: 'Obs. Id',
    unit: null,
    description: 'Internal ID given by the ObsTAP service.'
  },
  obs_publisher_did: {
    displayName: 'Pub. DID',
    unit: null,
    description: 'ID for the Dataset given by the publisher.'
  },
  obs_creator_did: {
    displayName: 'Creator DID',
    unit: null,
    description: 'IVOA dataset identifier given by the creator.'
  },
  obs_title: {
    displayName: 'Title',
    unit: null,
    description: 'Brief description of dataset in free format.'
  },
  dataproduct_type: {
    displayName: 'Product type',
    unit: null,
    description: 'Data product (file content) primary type.'
  },
  dataproduct_subtype: {
    displayName: 'Subtype',
    unit: null,
    description: 'Data product specific type.'
  },
  calib_level: {
    displayName: 'Calibration level',
    unit: null,
    description: 'Calibration level of the observation: in {0, 1, 2, 3, 4}.'
  },
  target_name: {
    displayName: 'Target Name',
    unit: null,
    description: 'Object of interest.'
  },
  target_class: {
    displayName: 'Target Class',
    unit: null,
    description: 'Class of the Target object as in SSA.'
  },
  object: { displayName: 'Object', unit: null },
  s_ra: {
    displayName: 'RA',
    unit: 'deg',
    description: 'Central Spatial Position in ICRS Right ascension.'
  },
  s_dec: {
    displayName: 'Dec',
    unit: 'deg',
    description: 'Central Spatial Position in ICRS Declination.'
  },
  s_fov: {
    displayName: 'FoV',
    unit: 'deg',
    description: 'Estimated size of the covered region as the diameter of a containing circle.'
  },
  s_region: {
    displayName: 'Coverage',
    unit: null,
    description: 'Sky region covered by the data product (expressed in ICRS frame).'
  },
  s_resolution: {
    displayName: 'Space Res.',
    unit: 'deg',
    description: 'Spatial resolution of data as FWHM of PSF.'
  },

  t_min: {
    displayName: 'T_min',
    unit: 'd',
    description: 'Start time in MJD.'
  },
  t_max: {
    displayName: 'T_max',
    unit: 'd',
    description: 'Stop time in MJD.'
  },
  t_exptime: {
    displayName: 'Exp. Time',
    unit: 's',
    description: 'Total exposure time.'
  },
  t_resolution: {
    displayName: 'Res. t',
    unit: 's',
    description: 'Temporal resolution FWHM.'
  },
  // date_obs: { displayName: 'Date Obs', unit: null },
  // time_obs: { displayName: 'Time Obs', unit: null },

  em_min: {
    displayName: 'λ_min',
    unit: 'm',
    description: 'start in spectral coordinates.'
  },
  em_max: {
    displayName: 'λ_max',
    unit: 'm',
    description: 'stop in spectral coordinates.'
  },
  em_ucd: {
    displayName: 'Spect. UCD',
    unit: null,
    description: 'Nature of the spectral axis.'
  },
  em_res_power: {
    displayName: 'λ/Δλ',
    unit: null,
    description: 'Value of the resolving power along the spectral axis. (R).'
  },
  //em_resolution: {
  //  displayName: 'em_resolution',
  //  unit: 'm',
  //  description: 'Value of Resolution along the spectral axis.'
  //},
  o_ucd: {
    displayName: 'Obs. UCD',
    unit: null,
    description: 'Nature of the observable axis.'
  },
  pol_states: {
    displayName: 'Pol. States',
    unit: null,
    description: 'List of polarization states present in the data file.'
  },

  preview: { displayName: 'Preview', unit: null },
  source_table: { displayName: 'Source Table', unit: null },
  facility_name: { displayName: 'Facility', unit: null },

  instrument_name: {
    displayName: 'Instrument',
    unit: null,
    description: 'The name of the instrument used for the observation.'
  },
  s_xel1: {
    displayName: '|X|',
    unit: null,
    description: 'Number of elements along the first coordinate of the spatial axis.'
  },
  s_xel2: {
    displayName: '|Y|',
    unit: null,
    description: 'Number of elements along the second coordinate of the spatial axis.'
  },
  t_xel: {
    displayName: '|t|',
    unit: null,
    description: 'Number of elements along the time axis.'
  },
  em_xel: {
    displayName: '|λ|',
    unit: null,
    description: 'Number of elements along the spectral axis.'
  },
  pol_xel: {
    displayName: '|Pol|',
    unit: null,
    description: 'Number of elements along the polarization axis.'
  },
  s_pixel_scale: {
    displayName: 'Pix. Scale',
    unit: 'arcsec',
    description: 'Sampling period in world coordinate units along the spatial axis.'
  },
  obs_collection: {
    displayName: 'Collection',
    unit: null,
    description: 'Name of the data collection.'
  },

  access_url: {
    displayName: 'Access URL',
    unit: null,
    description: 'URL used to access dataset.'
  },
  access_format: {
    displayName: 'Media Type',
    unit: null,
    description: 'Content format of the dataset.'
  },
  access_estsize: {
    displayName: 'Size',
    unit: 'kbyte',
    description: 'Estimated size of dataset: in kilobytes.'
  },

  ra_pnt: { displayName: 'Ra_pnt', unit: 'deg' },
  dec_pnt: { displayName: 'Dec_pnt', unit: 'deg' },
  glon_pnt: { displayName: 'Glon_pnt', unit: 'deg' },
  glat_pnt: { displayName: 'Glat_pnt', unit: 'deg' },

  deadc: { displayName: 'Deadc', unit: null },
  muoneff: { displayName: 'Muoneff', unit: null },
  event_count: { displayName: 'Event_count', unit: null },
  offset_obj: { displayName: 'Offset_obj', unit: 'deg' },
  safe_energy_lo: { displayName: 'Safe_energy_lo', unit: 'TeV' },
  safe_energy_hi: { displayName: 'Safe_energy_hi', unit: 'TeV' },

};

// Helper function to get display info
export const getColumnDisplayInfo = (backendName) => {
  const config = obsCoreColumnConfig[backendName.toLowerCase()] ||
                 obsCoreColumnConfig[backendName] ||
                 { displayName: backendName, unit: null, description: `${backendName}` };
  return {
    displayName: config.displayName || backendName,
    unit: config.unit,
    description: config.description || `${backendName}`
  };
};
