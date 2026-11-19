# Battle AI arena (11/17). Fresh container per fight; run with --network none (see ../arena.sh).
FROM debian:stable-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 procps nano less file \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd arena && useradd -m -s /bin/bash -G arena fighter_a && useradd -m -s /bin/bash -G arena fighter_b \
    && chmod 700 /home/fighter_a /home/fighter_b
COPY seed/ /arena-seed/
COPY start.sh /start.sh
RUN chmod 755 /start.sh
CMD ["/start.sh"]
