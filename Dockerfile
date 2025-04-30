FROM python:3.12

# Set the working directory
WORKDIR /app


# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the application code
COPY /src/ /app/

# Expose the Flask app port
EXPOSE 5000

# Command to run the Flask app
CMD ["python", "api.py"]
