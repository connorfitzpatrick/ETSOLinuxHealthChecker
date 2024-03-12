Run backend by cding into myBackend and running:

- `python manage.py runserver 8000`

Run frontend by cding into frontend and running:

- `npm start`

Zookeeper:

- `cd downloads/kafka_2.13-3.6.1`
- `bin/zookeeper-server-start.sh config/zookeeper.properties`
- If you are getting errors for a missing snapshot, go into the hidden `/tmp/zookeeper/version-2` and delete the log files
- Then go into `kafka-logs` and delete the meta.properties file
- Restart the Zookeeper, then Kafka
- If a complete reset of kafka and zookeeper is necessary, delete both of those log direcories in /tmp

Kafka:

- Start after zookeeper is up
- `cd downloads/kafka_2.13-3.6.1`
- `bin/kafka-server-start.sh config/server.properties`

Set up Docker containers by cding into docker and running:

- `docker run -p 58897:22 server1`

To rebuild docker:

- `docker-compose down`
- `docker-compose build`
- `docker compose up -d`

How to SSH into docker container via command line:

- `ssh <username>@<hostname> -p <container_port>`
- Ex: `ssh remote_user@localhost -p 2201`

If you get an error for the key having changed enter this command:

- `ssh-keygen -R "[localhost]:2204"`

`cd` into backend
run `source venv/bin/activate` on MacOS

- On Windows run `venv\Scripts\activate`
- `flask run`
