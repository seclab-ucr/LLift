# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory in the container
WORKDIR /app


# Install curl or wget, if not already available
RUN apt-get update && apt-get install -y curl


# # Copy the current directory contents into the container at /usr/src/app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt


# Download and extract the Linux kernel source
RUN curl -L https://cdn.kernel.org/pub/linux/kernel/v4.x/linux-4.14.tar.xz | tar -xJ


# Run bash when the container launches
CMD ["/bin/bash"]
