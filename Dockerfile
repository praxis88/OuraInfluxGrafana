FROM python:3.12-slim-bookworm

WORKDIR /etc/oura

RUN apt-get update && apt-get install -y \
apt-utils \
tzdata \
ca-certificates \
curl && \
apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

#Copy Files
COPY etc/ /etc

#Make executables
RUN chmod +x /etc/oura/oura_post_to_influxdb.py \
            /etc/oura/oura_delete_timerange.sh 

RUN ln -sf /usr/share/zoneinfo/America/Chicago /etc/localtime && \
    echo "America/Chicago" > /etc/timezone

CMD ["sleep", "infinity"]
