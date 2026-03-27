#!/bin/bash
set -e

echo ">>> MongoDB ECS ReplicaSet entrypoint (race condition safe + quorum wait)"

DATA_DIR="/data/db"
FLAG_FILE="$DATA_DIR/.mongo-initialized"
RS_NAME="rs0"

NODE_IPS=("10.0.1.10" "10.0.2.10" "10.0.3.10")
THIS_NODE_IP=$(ip route get 1 | awk '{print $7}')

echo ">>> IP du noeud : $THIS_NODE_IP"

wait_for_mongo () {
  until mongosh --quiet --host 127.0.0.1 --eval "db.adminCommand('ping')" >/dev/null 2>&1; do
    echo "⏳ Attente MongoDB local..."
    sleep 2
  done
}

wait_for_all_nodes () {
  echo ">>> Attente que tous les membres soient accessibles..."
  for host in "${NODE_IPS[@]}"; do
    until mongosh --quiet --host "$host" --eval "db.adminCommand('ping')" >/dev/null 2>&1; do
      echo "⏳ $host pas encore prêt..."
      sleep 2
    done
    echo "✅ $host prêt"
  done
}

if [ -f "$FLAG_FILE" ]; then
  echo "✅ Mongo déjà initialisé (flag présent)"
  echo ">>> Démarrage direct avec --auth"
  exec mongod \
    --replSet "$RS_NAME" \
    --keyFile /etc/mongo-keyfile/mongo-keyfile \
    --bind_ip_all \
    --auth
fi

echo "🆕 Première initialisation MongoDB"

mongod \
  --replSet "$RS_NAME" \
  --keyFile /etc/mongo-keyfile/mongo-keyfile \
  --bind_ip_all \
  --fork \
  --logpath /var/log/mongodb.log

wait_for_mongo

echo ">>> Vérification de l'état du ReplicaSet"
IS_INIT=$(mongosh --quiet --eval "try { rs.status().ok } catch(e) { 0 }")
if [ "$IS_INIT" != "1" ]; then
  wait_for_all_nodes

  echo "🚀 Initialisation du ReplicaSet"
  mongosh <<EOF
try {
  rs.initiate({
    _id: "$RS_NAME",
    members: [
      { _id: 0, host: "${NODE_IPS[0]}:27017" },
      { _id: 1, host: "${NODE_IPS[1]}:27017" },
      { _id: 2, host: "${NODE_IPS[2]}:27017" }
    ]
  })
} catch(e) {
  print("⚠️ ReplicaSet déjà initialisé ou erreur : " + e)
}
EOF

  echo "⏳ Attente élection PRIMARY..."
  until mongosh --quiet --eval "rs.isMaster().ismaster" | grep true >/dev/null; do
    sleep 2
  done

  echo "🔐 Création utilisateur admin"
  mongosh <<EOF
use admin
db.createUser({
  user: "root",
  pwd: "root",
  roles: [ { role: "root", db: "admin" } ]
})
EOF
else
  echo "➕ ReplicaSet déjà initialisé ou ce nœud est secondaire"
fi

touch "$FLAG_FILE"

echo "🔄 Redémarrage MongoDB avec --auth"
mongod --shutdown

exec mongod \
  --replSet "$RS_NAME" \
  --keyFile /etc/mongo-keyfile/mongo-keyfile \
  --bind_ip_all \
  --auth
