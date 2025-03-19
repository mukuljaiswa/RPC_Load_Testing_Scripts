from locust import HttpUser, task, between

class MyUser(HttpUser):
    # Set the base host for all requests
    host = "https://api-explorer.devdomain123.com"

    wait_time = between(0.5, 1.5)

    @task
    def get_safe_block_details(self):
        worker_id = self.environment.runner.worker_index
        print(f"Worker {worker_id} is executing the task")
        
        # Define the endpoint and query parameters
        endpoint = "/v1/api/block/getSafeBlockDetails"
        params = {"chain": "EVM"}

        # Make the GET request
        # response = self.client.get(endpoint, params=params)

        # # Print the response status and content (optional)
        # print(f"Worker {worker_id} - Response status code: {response.status_code}")
