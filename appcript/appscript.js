const SHEET_ID = "18KYPnVSOQF6I2Lm5P1j5nFx1y1RXSmfMWf9jBR2WJ-Q";
const TOMAS_SHEET_NAME = "Hoja1";
const CONFIG_SHEET_NAME = "Config";

function doGet(e) {

  const action = e.parameter.action;

  if (action == "get_plan_history") {
    return getPlanHistory();
  } else if (action == "get_config") {
    return getConfig();
  }

  return ContentService.createTextOutput("Unknown GET action").setMimeType(ContentService.MimeType.TEXT);
}

function doPost(e) {
  const requestData = JSON.parse(e.postData.contents);
  const action = requestData.action;

  if (action == "get_plan_history") {
    // Leemos el parámetro sheetName, por defecto "Plan Tiempo"
    var sheetName = e.parameter.sheetName || "Plan Tiempo";
    return getPlanHistory(sheetName);
  }else if (action == "delete_last") {
    return deleteLastRow();
  } else if (action == "save_plan_history") {
    return savePlanHistory(requestData.data);
  } else if (action == "save_config") {
    return saveConfig(requestData.data);
  } else {
    return addRow(requestData);
  }
}

function getConfig() {
  try {
    const spreadsheet = SpreadsheetApp.openById(SHEET_ID);
    let sheet = spreadsheet.getSheetByName(CONFIG_SHEET_NAME);
    if (!sheet) {
      return ContentService.createTextOutput(JSON.stringify({status: "success", data: {}})).setMimeType(ContentService.MimeType.JSON);
    }

    const data = sheet.getDataRange().getValues();
    let config = {};
    for (let i = 0; i < data.length; i++) {
      if (data[i][0]) {
        let val = data[i][1];
        // Intentar mantener tipos numéricos
        if (!isNaN(val) && val !== "") val = Number(val);
        config[data[i][0]] = val;
      }
    }
    return ContentService.createTextOutput(JSON.stringify({status: "success", data: config})).setMimeType(ContentService.MimeType.JSON);
  } catch (e) {
    return ContentService.createTextOutput(JSON.stringify({status: "error", message: e.toString()})).setMimeType(ContentService.MimeType.JSON);
  }
}

function saveConfig(newConfig) {
  try {
    const spreadsheet = SpreadsheetApp.openById(SHEET_ID);
    let sheet = spreadsheet.getSheetByName(CONFIG_SHEET_NAME);
    if (!sheet) {
      sheet = spreadsheet.insertSheet(CONFIG_SHEET_NAME);
    }

    let currentConfig = {};
    const lastRow = sheet.getLastRow();
    if (lastRow > 0) {
      const data = sheet.getRange(1, 1, lastRow, 2).getValues();
      for (let i = 0; i < data.length; i++) {
        currentConfig[data[i][0]] = data[i][1];
      }
    }

    for (let key in newConfig) {
      currentConfig[key] = newConfig[key];
    }

    sheet.clear();
    let rows = [];
    for (let key in currentConfig) {
      rows.push([key, currentConfig[key]]);
    }

    if (rows.length > 0) {
      sheet.getRange(1, 1, rows.length, 2).setValues(rows);
    }

    return ContentService.createTextOutput(JSON.stringify({status: "success"})).setMimeType(ContentService.MimeType.JSON);
  } catch (e) {
    return ContentService.createTextOutput(JSON.stringify({status: "error", message: e.toString()})).setMimeType(ContentService.MimeType.JSON);
  }
}

function addRow(data) {
  try {
    const sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(TOMAS_SHEET_NAME);
    const saldo = data.saldo !== undefined ? data.saldo : "";
    sheet.appendRow([data.fecha, data.hora, data.ml, saldo]);
    return ContentService.createTextOutput(JSON.stringify({status: "success"})).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({status: "error", message: err.toString()})).setMimeType(ContentService.MimeType.JSON);
  }
}

function deleteLastRow() {
  try {
    const sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(TOMAS_SHEET_NAME);
    const lastRow = sheet.getLastRow();
    if (lastRow > 1) {
      sheet.deleteRow(lastRow);
      return ContentService.createTextOutput(JSON.stringify({status: "success"})).setMimeType(ContentService.MimeType.JSON);
    }
    return ContentService.createTextOutput(JSON.stringify({status: "error", message: "Sheet is empty"})).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({status: "error", message: err.toString()})).setMimeType(ContentService.MimeType.JSON);
  }
}
function getPlanHistory(sheetName) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
  if (!sheet) {
    return ContentService.createTextOutput(JSON.stringify({status: 'success', data: []})).setMimeType(ContentService.MimeType.JSON);
  }

  var data = sheet.getDataRange().getValues();
  var headers = data[0];
  var rows = data.slice(1);
  var result = [];

  for (var i = 0; i < rows.length; i++) {
    var obj = {};
    for (var j = 0; j < headers.length; j++) {
      obj[headers[j]] = rows[i][j];
    }
    result.push(obj);
  }

  return ContentService.createTextOutput(JSON.stringify({status: 'success', data: result})).setMimeType(ContentService.MimeType.JSON);
}

function savePlanHistory(data, sheetName) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(sheetName);

  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
  }

  sheet.clear();

  if (data.length > 0) {
    var headers = Object.keys(data[0]);
    var values = [headers];

    for (var i = 0; i < data.length; i++) {
      var row = [];
      for (var j = 0; j < headers.length; j++) {
        row.push(data[i][headers[j]]);
      }
      values.push(row);
    }

    sheet.getRange(1, 1, values.length, headers.length).setValues(values);
  }

  return ContentService.createTextOutput(JSON.stringify({status: 'success'})).setMimeType(ContentService.MimeType.JSON);
}