# Sword-Challenge

# 🏥 Patient Evaluation Logic and Recommendations  

##  Patient Registration Process 
1. **Add new patient**  
   - If the patient is **not** in the database (verified by `first_name` and `last_name`), he or she will be **registered**.

2. **Update existing patient**  
   - If the patient **is already registered**, check if there are any **changes in their data** (`bmi`, `age`, `chronic_pain`, `recent_surgery`, etc.). 
   - If there are changes, the patient data is **updated in the database**.  

3. **Keep data unchanged**  
   - If the patient is already registered and their data **has not changed**, **no action** will be performed.  

##  Recommendations Process
1. **Add first recommendations**  
   - Patient information such as name, age, BMI, etc. is entered (recorded in the patient table). Based on the patient's health status, specific recommendations are created, **which are then included in the recommendation table**. For each recommendation, the timestamp (date and time) in which it was generated is also recorded. This allows you to retrieve the most recent recommendations in the future or identify the last recommendation made for the patient, if necessary.

2. **Add new recommendations for a new patient condition.**  
   - **If the patient entered is the same** (`first_name` and `last_name` are already in the patient table) but his conditions are different, new conditions are generated for him and are entered into the database. **Some may have the same recommendation (Physical Therapy...) but each one has a different id that distinguishes them**.

3. **Patient with the same conditions**  
   - **If the patient is the same and presents the same conditions**, the data is not reinserted into the database. Instead, information is retrieved from the cache, avoiding overloading the database with too much repeated data.

##  Motivation for this Logic  
Although the real world scenario is for a patient to have doctor appointments on different days, **there is the possibility that a patient may have more than one appointment per day (different doctors or even the same doctor)**. This way, more than one recommendation per day can be assigned to the same patient.   


##  Clinical Recommendation Process - The system returns **more than one recommendation** for a patient if necessary, considering their medical conditions.
- The structure of **if statements** is designed so that the **order of recommendations in the list reflects priority**.
- The recommendation **"Post-Op Rehabilitation Plan"** has **higher priority**, while **"Weight Management Program"** has **lower priority**.
- Although this approach is **not essential to the current problem**, it may be **useful in the future** when refining clinical recommendations.
