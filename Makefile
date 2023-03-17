DIRNAME := $(shell basename $$(pwd))

run:
	bash go.sh

test:
	echo $(DIRNAME)

clean:
	docker container prune -f
	docker images | awk '/$(DIRNAME)/ {print $$3}' | xargs -r docker rmi
	docker system prune -f
