#!/bin/bash

echo "⏳ Attente du démarrage de MongoDB..."
sleep 15

echo "🚀 Initialisation du Replica Set..."

mongosh --host mongo1:27017 <<EOF
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo1:27017" },
    { _id: 1, host: "mongo2:27017" },
    { _id: 2, host: "mongo3:27017" }
  ]
})
EOF

echo "⏳ Attente de l’élection du PRIMARY..."
sleep 10

echo "👤 Création de l'utilisateur admin..."

mongosh --host mongo1:27017 <<EOF
use admin
db.createUser({
  user: "root",
  pwd: "root",
  roles: [
    { role: "root", db: "admin" }
  ]
})
EOF

echo "✅ Replica Set initialisé et utilisateur admin créé."
