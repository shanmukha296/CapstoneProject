# Viva Preparation: Nationwide Crime Safety System

## Top 25 Technical Questions & Concepts

### Geospatial & Database Optimization
1. **What is the Haversine formula and why is it used?**
   - It calculates the great-circle distance between two points on a sphere given their longitudes and latitudes. Used for accurate distance over the Earth's surface.
2. **How do you optimize 10,000+ spatial queries in SQLite?**
   - Using R*Tree spatial indexes or composite indexes on (lat, lng) to minimize full table scans.
3. **What is the complexity of your current police search algorithm?**
   - Currently O(N) due to manual distance calculation, but the database use of indexes on `state` reduces N significantly.
4. **Why use SQLite for a national application?**
   - Ideal for local development, mobile integration, and capstone projects due to its zero-configuration nature and performance for read-heavy safety data.
5. **How does the `idx_state_district` composite index improve performance?**
   - It allows the database to instantly filter stations by region before calculating distances, reducing CPU cycles.

### Flask & SQLAlchemy
6. **Explain the `init_police_db()` seeding strategy.**
   - Uses `bulk_save_objects` to efficiently insert hundreds of records in a single transaction, preventing I/O bottlenecks.
7. **What is the benefit of the `scoped_session` in Flask-SQLAlchemy?**
   - Ensures thread-safety when handling multiple API requests from different users simultaneously.
8. **Why is the `police_stations` table indexed on the `state` column?**
   - Because the frontend often filters results by state, making this the most frequent search parameter.
9. **Explain the difference between `db.create_all()` and manual migrations.**
   - `db.create_all()` is for initial schema creation; migrations (Alembic) are for evolving the schema without losing data.
10. **How do you handle precision for latitude and longitude in SQLAlchemy?**
    - Using the `db.Float` type with appropriate decimal rounding in the business logic to ensure <1m accuracy.

### Real-Time & Frontend
11. **Explain the 5-second GPS update loop.**
    - Uses `setInterval` to trigger `navigator.geolocation.getCurrentPosition`, ensuring the "Nearest PS" always reflects the user's current position while traveling.
12. **Why use `tel:` protocol links in the popup?**
    - To provide instant emergency calling capabilities on mobile devices with a single tap.
13. **How is the NCRB 2025 crime rate data utilized?**
    - It's used for color-coding hotspots (Red > 1500) and providing context-aware safety alerts.
14. **What is the purpose of the 200m safety radius on police markers?**
    - Visual representation of the "Safe Zone" around an active police precinct.
15. **How does the app handle background location updates?**
    - Via the `watchPosition` or frequent polling intervals, ensuring real-time response even if the browser is minimized.

### System Architecture
16. **Explain the Transfer Learning implementation.**
    - Using spatial similarity to generalize crime risk across cities without retraining models for every district.
17. **How is the XGBoost model integrated into the routing logic?**
    - Each coordinate segment of the Google Maps route is passed to the model to evaluate a safety score (0-100).
18. **Why use a BiLSTM model for crime forecasting?**
    - To capture long-term temporal dependencies and seasonality in crime data (e.g., weekend vs weekday shifts).
19. **What security measures are implemented for user data?**
    - Password hashing using `werkzeug.security` (PBKDF2) to prevent plain-text theft.
20. **How does the ambulance (108) feature work?**
    - Integrated as a static emergency action triggered by high-risk route segments.

### Performance & Scalability
21. **What is the response time for `/api/police_search`?**
    - Optimized to <50ms for 528 stations by using state-level pre-filtering.
22. **What would you change to support 1 million stations?**
    - Implement a proper Spatial Database like PostGIS or use H3 Hexagonal indexing.
23. **How do you handle API key security?**
    - Environment variables (OS.environ) to keep sensitive keys out of the source code.
24. **Explain the benefit of the `ratio ratio-16x9` in the CCTV modal.**
    - Ensures responsive video scaling across different screen sizes.
25. **What is the role of YOLOv8 in the system?**
    - Real-time object detection for identifying weapons/threats in surveillance feeds.
