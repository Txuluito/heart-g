# Actualización necesaria en Google Apps Script

Para que el sistema funcione correctamente con las dos hojas de planificación ("Plan Tiempo" y "Plan Dosis"), debes asegurarte de que tu script de Google Apps Script maneje el parámetro `sheetName`.

Aquí tienes un ejemplo de cómo debería lucir la lógica para `get_plan_history` y `save_plan_history`:

```javascript
function doGet(e) {
  var action = e.parameter.action;
  
  if (action == "get_plan_history") {
    // Leemos el parámetro sheetName, por defecto "Plan Tiempo"
    var sheetName = e.parameter.sheetName || "Plan Tiempo";
    return getPlanHistory(sheetName);
  }
  // ... otros actions ...
}

function doPost(e) {
  var request = JSON.parse(e.postData.contents);
  var action = request.action;
  
  if (action == "save_plan_history") {
    // Leemos el parámetro sheetName, por defecto "Plan Tiempo"
    var sheetName = request.sheetName || "Plan Tiempo";
    return savePlanHistory(request.data, sheetName);
  }
  // ... otros actions ...
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
```
