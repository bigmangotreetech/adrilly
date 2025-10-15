# QR Attendance API Contracts

## Generate QR Code
**Endpoint:** `POST /mobile-api/attendance/generate-qr`  
**Authentication:** Required (Admin/Coach only)  
**Description:** Generate a signed QR code for attendance marking

### Request Body
```json
{
  "type": "center" | "class",
  "center_id": "string", // Required if type is "center"
  "class_id": "string"   // Required if type is "class"
}
```

### Response
```json
{
  "qrCode": "string",           // Base64 encoded signed token
  "type": "center" | "class",   // Type of QR code generated
  "validUntil": "ISO8601",      // Token expiry timestamp
  "message": "string"           // Success message
}
```

### Error Responses
- `400`: Invalid type or missing required fields
- `404`: Center/Class not found
- `500`: Internal server error

---

## Mark Attendance via QR
**Endpoint:** `POST /mobile-api/attendance/mark`  
**Authentication:** Required (Student only)  
**Description:** Mark attendance by scanning a QR code

### Request Body
```json
{
  "qrCode": "string"  // Base64 encoded QR token from scan
}
```

### Response
```json
{
  "success": true,
  "classId": "string",     // ID of the class
  "className": "string",   // Name of the class
  "message": "string"      // Success/failure message
}
```

### Error Responses
- `400`: Invalid or expired QR code, no active class found
- `403`: User not enrolled in class or not a student
- `500`: Internal server error

---

## QR Token Format
QR codes contain a signed, base64-encoded JSON token with the following structure:

```json
{
  "payload": {
    "center_id": "string",      // For center-based QR
    "class_id": "string",       // For class-based QR
    "type": "center" | "class", // QR type
    "issued_at": "ISO8601",     // Token creation time
    "expires_at": "ISO8601"     // Token expiry time (15 minutes)
  },
  "signature": "string"         // HMAC-SHA256 signature
}
```

### Security Features
- **HMAC Signature**: Prevents token forgery
- **Time-based Expiry**: Tokens expire after 15 minutes
- **Type Validation**: Ensures proper QR code usage
- **Role-based Access**: Only coaches/admins can generate, only students can scan

### Time Windows
- **Center QR**: Resolves to classes within ±15 minutes of scan time
- **Class QR**: Valid from 30 minutes before to 4 hours after scheduled time
