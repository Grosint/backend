from fastapi import status


class TestUser:
    """Test user endpoints"""

    def test_create_user_success(self, client):
        """Test successful user creation"""
        user_data = {
            "email": "newuser@example.com",
            "phone": "+1234567890",
            "password": "newpassword123",
            "verifyByGovId": True,
        }

        response = client.post("/api/user/", json=user_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "user_id" in data
        assert data["user"]["email"] == user_data["email"]

    # def test_create_user_duplicate_email(self, client, test_user):
    #     """Test user creation with duplicate email"""
    #     user_data = {
    #         "email": test_user.email,
    #         "username": "differentuser",
    #         "password": "password123",
    #         "full_name": "Different User"
    #     }

    #     response = client.post("/api/v1/users/", json=user_data)

    #     assert response.status_code == status.HTTP_400_BAD_REQUEST

    # def test_create_user_invalid_email(self, client):
    #     """Test user creation with invalid email"""
    #     user_data = {
    #         "email": "invalid-email",
    #         "username": "testuser",
    #         "password": "password123",
    #         "full_name": "Test User"
    #     }

    #     response = client.post("/api/v1/users/", json=user_data)

    #     assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # def test_get_current_user(self, client, auth_headers, test_user):
    #     """Test getting current user information"""
    #     response = client.get("/api/v1/users/me", headers=auth_headers)

    #     assert response.status_code == status.HTTP_200_OK
    #     data = response.json()
    #     assert data["email"] == test_user.email
    #     assert data["username"] == test_user.username

    # def test_update_current_user(self, client, auth_headers):
    #     """Test updating current user information"""
    #     update_data = {
    #         "full_name": "Updated Name"
    #     }

    #     response = client.put(
    #         "/api/v1/users/me",
    #         json=update_data,
    #         headers=auth_headers
    #     )

    #     assert response.status_code == status.HTTP_200_OK
    #     data = response.json()
    #     assert data["full_name"] == update_data["full_name"]

    # def test_list_users(self, client, auth_headers):
    #     """Test listing users"""
    #     response = client.get("/api/v1/users/", headers=auth_headers)

    #     assert response.status_code == status.HTTP_200_OK
    #     data = response.json()
    #     assert "users" in data
    #     assert "total" in data
