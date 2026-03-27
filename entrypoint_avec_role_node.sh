#!/bin/bash
set -e

echo ">>> Démarrage Mongo - rôle=$MONGO_ROLE node=$MONGO_NODE_ID"

FLAG_FILE="/data/db/.mongo-initialized"

echo ">>> Lancement mongod (sans auth)"
mongod --replSet rs0 \
       --keyFile /etc/mongo-keyfile/mongo-keyfile \
       --bind_ip_all \
       --fork \
       --logpath /var/log/mongodb.log

echo ">>> Attente du démarrage Mongo local..."
until mongosh --eval "db.adminCommand('ping')" > /dev/null 2>&1; do
  sleep 2
done

if [[ "$MONGO_ROLE" == "INIT" && ! -f "$FLAG_FILE" ]]; then
  echo ">>> Ce noeud initialise le ReplicaSet"

  echo ">>> Attente des autres noeuds..."
  for host in $MONGO_RS_MEMBERS; do
    until mongosh --host "$host" --eval "db.adminCommand('ping')" > /dev/null 2>&1; do
      echo "⏳ $host pas prêt"
      sleep 2
    done
    echo "✅ $host prêt"
  done

  mongosh <<EOF
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "$MONGO_RS_MEMBER_1" },
    { _id: 1, host: "$MONGO_RS_MEMBER_2" },
    { _id: 2, host: "$MONGO_RS_MEMBER_3" }
  ]
})

var maxTries = 60;
while (!rs.isMaster().ismaster && maxTries--) {
  print("⏳ En attente PRIMARY...");
  sleep(1000);
}

use admin
db.createUser({
  user: "$MONGO_ROOT_USER",
  pwd: "$MONGO_ROOT_PASSWORD",
  roles: [{ role: "root", db: "admin" }]
})
EOF

  touch "$FLAG_FILE"
  echo "✅ ReplicaSet initialisé"
fi

echo ">>> Redémarrage mongod avec --auth"
mongod --shutdown

exec mongod --replSet rs0 \
            --keyFile /etc/mongo-keyfile/mongo-keyfile \
            --bind_ip_all \
            --auth
