### Running the Server using Singularity

#### Download Docker Image

```
singularity pull --name mskcc-ridgeback-1.0.0-rc1.img docker://mskcc/ridgeback:1.0.0-rc1
```

##### Starting an instance

```
singularity instance start --bind <ridgeback_install_directory>:/ridgeback_server mskcc-ridgeback-1.0.0-rc1.img ridgeback
```

##### Running the server at port 4003 

```
singularity run instance://ridgeback python3 /ridgeback_server/manage.py runserver 0.0.0.0:4003
```

