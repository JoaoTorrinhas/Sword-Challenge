import pytest
import httpx
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import text
from unittest.mock import patch, AsyncMock
from main import app, get_db, get_current_user, redis_client
import json
 
# Creating a test database to test the endpoints
engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

# Create and drop tables
async def create_tables():
    async with engine.begin() as conn:
        await conn.execute(text(
            """
            CREATE TABLE patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                age INTEGER NOT NULL,
                bmi REAL NOT NULL,
                chronic_pain BOOLEAN NOT NULL,
                recent_surgery BOOLEAN NOT NULL
            )
            """
        ))
        await conn.execute(text(
            """
            CREATE TABLE recommendations (
                id TEXT PRIMARY KEY,
                patient_id INTEGER NOT NULL,
                recommendation TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE
            )
            """
        ))

async def drop_tables():
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS recommendations"))
        await conn.execute(text("DROP TABLE IF EXISTS patients"))

@pytest.fixture(scope="module", autouse=True)
async def setup_database():
    await create_tables()
    yield
    await drop_tables()

@pytest.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session

@pytest.fixture
async def override_get_db():
    async def get_test_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = get_test_db
    yield 
    app.dependency_overrides.clear()
  
    
@pytest.fixture
async def override_redis(mock_redis):
    app.dependency_overrides[redis_client] = mock_redis
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_get_current_user():
    async def fake_user():
        # Fake valid user for authentication
        return {"username": "admin"} 

    return fake_user  

@pytest.fixture
async def async_client(mock_get_current_user):
    app.dependency_overrides[get_current_user] = mock_get_current_user  

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear() 

@pytest.fixture
def mock_redis():
    with patch("main.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.get.return_value = json.dumps({
            "id": "1",
            "patient_id": 1,
            "recommendation": "General Health Checkup",
            "timestamp": "2025-03-16T19:56:28.855702"
        })
        mock_redis.set.return_value = AsyncMock()
        mock_redis.delete.return_value = AsyncMock()
        mock_redis.publish.return_value = AsyncMock()
        yield mock_redis


@pytest.mark.anyio
@pytest.mark.parametrize(
    "patient_data",
    [
        {"first_name": "Alex", "last_name": "Doe", "age": 30, "bmi": 37.0, "chronic_pain": False, "recent_surgery": False},
        {"first_name": "Josh", "last_name": "Nate", "age": 67, "bmi": 37.0, "chronic_pain": True, "recent_surgery": False},
        {"first_name": "Nate", "last_name": "Josh", "age": 30, "bmi": 37.0, "chronic_pain": False, "recent_surgery": True},
        {"first_name": "Jane", "last_name": "Smith", "age": 68, "bmi": 28.5, "chronic_pain": True, "recent_surgery": False},
        {"first_name": "Bob", "last_name": "Johnson", "age": 25, "bmi": 27, "chronic_pain": False, "recent_surgery": True},
        {"first_name": "Kika", "last_name": "Nunes", "age": 67, "bmi": 35, "chronic_pain": True, "recent_surgery": True},
    ],
)
async def test_evaluate_new_patient(async_client: AsyncClient, mock_redis: AsyncMock, db_session: AsyncSession, override_get_db, patient_data):
    mock_redis.get.return_value = None  

    response = await async_client.post("/evaluate", json=patient_data)
    
    #print(f"RESPONSE FOR {patient_data['first_name']} {patient_data['last_name']}: ", response.json())

    assert response.status_code == 200
    assert "recommendations" in response.json()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "patient_data, cached_recommendations",
    [
        ({"first_name": "John", "last_name": "Doe", "age": 30, "bmi": 25.0, "chronic_pain": False, "recent_surgery": True}, ["Post-Op Rehabilitation Plan"]),
        ({"first_name": "Jane", "last_name": "Smith", "age": 65, "bmi": 28.5, "chronic_pain": True, "recent_surgery": False}, ["Physical Therapy"]),
        ({"first_name": "Bob", "last_name": "Johnson", "age": 18, "bmi": 32.2, "chronic_pain": False, "recent_surgery": False}, ["Weight Management Program"]),
        ({"first_name": "Josh", "last_name": "Nate", "age": 67, "bmi": 37.0, "chronic_pain": True, "recent_surgery": False}, ["Physical Therapy", "Weight Management Program"]),
        ({"first_name": "Nate", "last_name": "Josh", "age": 30, "bmi": 37.0, "chronic_pain": False, "recent_surgery": True}, ["Post-Op Rehabilitation Plan", "Weight Management Program"]),
        ({"first_name": "Kika", "last_name": "Nunes", "age": 67, "bmi": 35, "chronic_pain": True, "recent_surgery": True}, ["Post-Op Rehabilitation Plan", "Physical Therapy", "Weight Management Program"]),
    ],
)
async def test_evaluate_patient_with_cached_recommendations(async_client: AsyncClient, mock_redis: AsyncMock, db_session: AsyncSession, override_get_db, patient_data, cached_recommendations):
    mock_redis.get.return_value = json.dumps(cached_recommendations)  
    response = await async_client.post("/evaluate", json=patient_data)
    
    #print(f"RESPONSE FOR {patient_data['first_name']} {patient_data['last_name']}: ", response.json())

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["recommendations"] == cached_recommendations


@pytest.mark.anyio
async def test_get_recommendation_by_id(setup_database, db_session, mock_redis, async_client, override_redis):
    await db_session.execute(text("DELETE FROM recommendations"))
    await db_session.execute(text("DELETE FROM patients"))
    await db_session.commit()

    # Simulate adding a patiente and a recommendation to the database so it can be retrieved afterwards for the test
    await db_session.execute(text(
        """
        INSERT INTO patients (id, first_name, last_name, age, bmi, chronic_pain, recent_surgery)
        VALUES (1, 'John', 'Doe', 30, 25.0, 0, 0)
        """
    ))

    await db_session.execute(text(
        """
        INSERT INTO recommendations (id, patient_id, recommendation, timestamp)
        VALUES ('1', 1, 'General Health Checkup', '2025-03-16T19:56:28.855702')
        """
    ))
    
    await db_session.commit()

    await mock_redis.set(f"recommendation:{'1'}", json.dumps({
        "id": "1",
        "patient_id": 1,
        "recommendation": "General Health Checkup",
        "timestamp": "2025-03-16T19:56:28.855702"
    }))

    response = await async_client.get("/recommendation/1")
    #print("Response test_get_recommendation_by_id: ", response.json())

    assert response.status_code == 200
    assert response.json() == {
        "id": "1",
        "patient_id": 1,
        "recommendation": "General Health Checkup",
        "timestamp": "2025-03-16T19:56:28.855702"
    }
    

@pytest.mark.anyio
async def test_get_recommendation_by_id_not_found(mock_redis, async_client, override_get_db, override_redis):
    mock_redis.get.return_value = None
    response = await async_client.get("/recommendation/999")
    #print("Response test_get_recommendation_by_id_not_found: ", response.json())
    assert response.status_code == 404
    assert response.json() == {"detail": "Recommendation not found"}
    

@pytest.mark.anyio
async def test_login_for_access_token_success(async_client):
    with patch("main.verify_password", return_value=True):
        response = await async_client.post("/token", data={"username": "admin", "password": "admin123"})
        assert response.status_code == 200
        json_response = response.json()
        assert "access_token" in json_response
        assert json_response["token_type"] == "bearer"

@pytest.mark.anyio
async def test_login_for_access_token_fail(async_client):
    with patch("main.verify_password", return_value=False):
        response = await async_client.post("/token", data={"username": "admin", "password": "wrong_password"})
        assert response.status_code == 401
        assert response.json() == {"detail": "Incorrect username or password"}
