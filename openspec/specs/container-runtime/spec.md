# container-runtime Specification

## Purpose
Define la entrega containerizada del proyecto: una imagen de la API construida desde el `Dockerfile` de la raíz y una orquestación con `docker-compose.yml` en la raíz que levanta la API junto con PostgreSQL y ejecuta la suite de pruebas.

## Requirements

### Requirement: Dockerfile en la raíz del repositorio
El repositorio SHALL contener un archivo `Dockerfile` en su directorio raíz que construya una imagen con la API y sus dependencias, y que arranque el servidor HTTP de la aplicación.

#### Scenario: Construcción de la imagen de la API
- **WHEN** se ejecuta la construcción de la imagen a partir del `Dockerfile` de la raíz del repositorio
- **THEN** la construcción termina con código de salida `0` y produce una imagen que incluye el código de la aplicación y sus dependencias

#### Scenario: Arranque del servidor en la imagen
- **WHEN** se inicia un contenedor generado por ese `Dockerfile`
- **THEN** el proceso de la API queda escuchando en el puerto `8000` del contenedor

### Requirement: docker-compose.yml en la raíz del repositorio
El repositorio SHALL contener un archivo `docker-compose.yml` en su directorio raíz que defina un servicio de PostgreSQL y un servicio de la API, ambos construidos o levantados desde la raíz, de modo que el proyecto se ejecute con un único `docker compose up --build`.

#### Scenario: Levantamiento completo con Compose
- **WHEN** se ejecuta `docker compose up --build` desde la raíz del repositorio
- **THEN** los servicios de PostgreSQL y de la API se crean sin errores y la API queda accesible

#### Scenario: La API es alcanzable desde el host
- **WHEN** la orquestación está levantada y se consulta el endpoint `GET /health` publicado por el servicio de la API
- **THEN** la respuesta tiene código `200` y el cuerpo JSON `{"status": "ok"}`

#### Scenario: La API alcanza a PostgreSQL por el nombre del servicio
- **WHEN** el servicio de la API registra un usuario mediante `POST /auth/register` dentro de la red de Compose
- **THEN** la API responde con código `201` porque la base de datos del servicio de PostgreSQL está disponible

### Requirement: Persistencia de los datos de PostgreSQL
El servicio de PostgreSQL de Compose SHALL almacenar sus datos en un volumen persistente que sobrevive a la recreación del contenedor.

#### Scenario: Los datos sobreviven a la recreación del contenedor
- **WHEN** se registra un usuario a través de la API, se detiene y se vuelve a levantar la orquestación con `docker compose up --build`
- **THEN** el usuario sigue existiendo en PostgreSQL y un nuevo `POST /auth/login` con sus credenciales responde con código `200`

### Requirement: La suite de pruebas se ejecuta dentro de la imagen
La orquestación de Compose SHALL incluir un servicio capaz de ejecutar la suite de pruebas dentro de la imagen construida, y dicho servicio SHALL terminar con código de salida `0` cuando todas las pruebas pasan.

#### Scenario: Ejecución de las pruebas en contenedor
- **WHEN** se ejecuta `docker compose up --build --abort-on-container-exit --exit-code-from tests` desde la raíz del repositorio
- **THEN** el comando termina con código de salida `0` y el servicio de pruebas informa que todas las pruebas pasaron

#### Scenario: La suite usa PostgreSQL real
- **WHEN** el servicio de pruebas se ejecuta contra la base de datos PostgreSQL de la orquestación
- **THEN** las pruebas de persistencia, como el registro de un usuario y la creación de un turno, se ejecutan sin errores de conexión

### Requirement: Configuración por variables de entorno
La imagen de la API SHALL obtener su configuración (cadena de conexión a la base de datos, secreto de firma del token y puerto) de variables de entorno, y el `docker-compose.yml` SHALL proporcionarlas al servicio de la API sin incrustar secretos de producción en el repositorio.

#### Scenario: El servicio de la API recibe su configuración
- **WHEN** la orquestación levanta el servicio de la API
- **THEN** el servicio se inicia con una cadena de conexión válida y sirve peticiones HTTP

### Requirement: El contenedor no incluye el entorno de desarrollo
La imagen de la API SHALL incluir únicamente lo necesario para ejecutar la aplicación y SHALL exponer el puerto `8000`.

#### Scenario: La imagen expone el puerto de la aplicación
- **WHEN** se publica el puerto `8000` del contenedor de la API
- **THEN** las peticiones HTTP al puerto publicado son atendidas por la API del contenedor
