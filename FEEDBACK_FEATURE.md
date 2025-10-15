# Student Feedback Feature Implementation

## Overview
This document describes the implementation of the student feedback feature for attended classes. Coaches can now provide structured feedback for students based on activity-specific metrics.

## Backend Implementation

### 1. Feedback Model (`app/models/feedback.py`)
Created a new `Feedback` model with the following fields:
- `class_id`: Reference to the class
- `student_id`: Reference to the student
- `coach_id`: Reference to the coach who provided feedback
- `activity_id`: Reference to the activity (obtained from schedule_item)
- `organization_id`: Reference to the organization
- `metrics`: Dictionary of metric names and ratings (1-5 scale)
- `notes`: Optional text notes
- `created_at` and `updated_at`: Timestamps

### 2. API Endpoints (`app/routes/mobile_api.py`)

#### GET `/mobile-api/classes/<class_id>/activity`
- Retrieves activity information for a class via its schedule_item_id
- Returns activity data including feedback_metrics array
- Required for determining which metrics to display in feedback form

#### POST `/mobile-api/classes/<class_id>/feedback`
- Submits or updates feedback for a student in a class
- Validates that student attended the class
- Gets activity_id via schedule_item_id from class
- Creates new feedback or updates existing feedback
- Request body:
  ```json
  {
    "metrics": {
      "Technique": 4,
      "Effort": 5,
      "Teamwork": 3
    },
    "notes": "Great improvement this week!"
  }
  ```

#### GET `/mobile-api/classes/<class_id>/feedback`
- Retrieves existing feedback for the current user in a class
- Returns null if no feedback exists
- Used to pre-populate feedback form when updating

### 3. Database Collections

#### `feedback` Collection
New MongoDB collection to store feedback documents with the structure defined by the Feedback model.

#### `activities` Collection
Already exists with `feedback_metrics` field:
- `feedback_metrics`: Array of strings representing metric names
- Examples: ["Technique", "Effort", "Teamwork", "Sportsmanship", "Attendance"]

## Mobile App Implementation

### 1. Feedback Model (`lib/models/feedback.dart`)
Created two Dart models:

#### `Activity`
- Represents activity information
- Contains `feedbackMetrics` list for rating categories

#### `ClassFeedback`
- Represents student feedback
- Contains metrics map and notes
- Supports JSON serialization/deserialization

### 2. API Service Methods (`lib/services/class_api_service.dart`)
Added three new methods to `ClassApiService`:

```dart
Future<ApiResponse<Map<String, dynamic>>> getClassActivity(String classId)
Future<ApiResponse<String>> submitClassFeedback(String classId, Map<String, int> metrics, String? notes)
Future<ApiResponse<Map<String, dynamic>?>> getClassFeedback(String classId)
```

### 3. Feedback Dialog Widget (`lib/widgets/feedback/feedback_dialog.dart`)
Created a comprehensive feedback submission dialog with:
- Dynamic rating metrics based on activity
- 1-5 star rating system with emoji icons
- Visual rating labels (Poor to Excellent)
- Optional notes field (max 500 characters)
- Update support for existing feedback
- Loading states and error handling

Key Features:
- Responsive design with max width constraint
- Material Design 3 styling
- Accessibility with tooltips and clear labels
- Form validation
- Success/error feedback via SnackBars

### 4. Class Detail Screen Updates (`lib/screens/classes/class_detail_screen.dart`)

#### Attended Students Tab Enhancement
Added feedback functionality for coaches:

1. **Feedback Card Header**
   - Displayed at the top of attended students list
   - Shows "Provide Feedback" prompt
   - Quick "Add" button for convenience
   - Only visible to coaches/admins

2. **Student Card Enhancement**
   - Added individual feedback button for each student
   - Shows "rate_review" icon
   - Tooltip: "Add Feedback"
   - Only visible to coaches/admins

3. **Feedback Flow**
   - Tapping feedback button loads activity metrics
   - Shows loading indicator during API calls
   - Opens FeedbackDialog with pre-populated data if feedback exists
   - Refreshes list after successful submission

## User Flow

### For Coaches/Admins:
1. Navigate to Class Detail Screen
2. Switch to "Attended" tab
3. See list of students who attended
4. Click "Add" button in header OR click feedback icon on individual student card
5. System loads activity feedback metrics
6. System checks for existing feedback and pre-populates if found
7. Coach rates student on each metric (1-5 scale)
8. Coach optionally adds notes
9. Coach submits feedback
10. System saves feedback to database
11. Success message displayed
12. List refreshes to show updated state

### For Students:
- Students can view their own feedback (future enhancement)
- Currently, feedback submission is coach-only

## Data Flow

```
Class -> schedule_item_id -> Schedule Item -> activity_id -> Activity -> feedback_metrics
```

1. Class document contains `schedule_item_id`
2. Schedule item contains `activity_id`
3. Activity contains `feedback_metrics` array
4. Feedback uses metrics to create rating inputs
5. Feedback is saved with references to class, student, activity, coach, and organization

## Security Considerations

1. **Authentication**: All endpoints require JWT authentication
2. **Authorization**: 
   - Only coaches/admins can submit feedback
   - Students must have attended the class (verified via attendance collection)
3. **Validation**:
   - Class ID must be valid
   - Student must exist and be active
   - Metrics must not be empty
   - Activity must exist for the class

## Future Enhancements

1. **Student View**: Allow students to view their feedback history
2. **Analytics**: Aggregate feedback data for progress tracking
3. **Bulk Feedback**: Allow coaches to rate multiple students at once
4. **Rich Metrics**: Support for different rating scales (1-10, pass/fail, etc.)
5. **Feedback Templates**: Pre-defined note templates for common scenarios
6. **Notifications**: Notify students when they receive feedback
7. **Reports**: Generate PDF reports of student progress over time

## Testing Checklist

### Backend:
- [ ] Test GET activity endpoint with valid class_id
- [ ] Test GET activity endpoint with invalid class_id
- [ ] Test POST feedback with valid data
- [ ] Test POST feedback without attendance record
- [ ] Test POST feedback updates existing feedback
- [ ] Test GET feedback returns existing feedback
- [ ] Test GET feedback returns null when no feedback exists

### Mobile App:
- [ ] Test feedback button visibility for coaches
- [ ] Test feedback button hidden for students
- [ ] Test loading activity metrics
- [ ] Test rating all metrics
- [ ] Test submitting feedback without notes
- [ ] Test submitting feedback with notes
- [ ] Test updating existing feedback
- [ ] Test error handling for network failures
- [ ] Test UI on different screen sizes

## Implementation Details

### Per-Student Feedback
- Each feedback entry is unique per (class_id, student_id) combination
- Coaches can provide individual feedback for each student who attended
- Feedback is stored with the coach_id who submitted it
- Updates to feedback preserve the original creation time but update the coach_id

### API Request/Response Examples

#### Submit Feedback (POST)
```json
{
  "student_id": "507f1f77bcf86cd799439011",
  "metrics": {
    "Technique": 4,
    "Effort": 5,
    "Teamwork": 3
  },
  "notes": "Great improvement this week!"
}
```

#### Get Feedback (GET)
Response:
```json
{
  "success": true,
  "feedback": {
    "id": "507f1f77bcf86cd799439012",
    "class_id": "507f1f77bcf86cd799439010",
    "student_id": "507f1f77bcf86cd799439011",
    "coach_id": "507f1f77bcf86cd799439013",
    "activity_id": "507f1f77bcf86cd799439014",
    "organization_id": "507f1f77bcf86cd799439015",
    "metrics": {
      "Technique": 4,
      "Effort": 5,
      "Teamwork": 3
    },
    "notes": "Great improvement this week!",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

## Known Limitations

1. Feedback metrics are static - defined at activity level, not customizable per class
2. No validation on rating values beyond 1-5 range
3. No support for different rating scales (could be extended to support 1-10, pass/fail, etc.)

## Files Changed

### Backend:
- `app/models/feedback.py` (NEW)
- `app/routes/mobile_api.py` (MODIFIED - added 3 endpoints)

### Mobile App:
- `lib/models/feedback.dart` (NEW)
- `lib/services/class_api_service.dart` (MODIFIED - added 3 methods)
- `lib/widgets/feedback/feedback_dialog.dart` (NEW)
- `lib/screens/classes/class_detail_screen.dart` (MODIFIED - added feedback UI)

## Dependencies

No new dependencies were added. The implementation uses existing packages:
- Backend: Flask, PyMongo, existing auth/validation infrastructure
- Mobile: Flutter Material Design, existing API service layer

## Deployment Notes

1. No database migrations required (MongoDB schema-less)
2. Ensure `feedback` collection is indexed on:
   - `class_id` and `student_id` (compound index for uniqueness)
   - `organization_id` (for organization-scoped queries)
   - `activity_id` (for activity analytics)
3. Consider adding indexes on `created_at` for time-based queries

