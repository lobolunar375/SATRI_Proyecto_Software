pipeline {
    agent {
        // Ejecutamos el pipeline dentro de un contenedor con Python
        // Montamos docker.sock para que Testcontainers pueda hacer Docker-out-of-Docker (DooD)
        docker {
            image 'python:3.11-slim'
            args '-v /var/run/docker.sock:/var/run/docker.sock'
        }
    }
    
    environment {
        // Definir variables de entorno adicionales si Testcontainers u otros lo requieren
        PYTHONUNBUFFERED = '1'
    }

    stages {
        stage('Checkout') {
            steps {
                // Checkout del código fuente
                checkout scm
            }
        }
        
        stage('Install Dependencies') {
            steps {
                // Nos movemos al directorio del servicio y preparamos el entorno virtual
                dir('backend-aks/brain/dashboard-soc') {
                    sh '''
                    python -m pip install --upgrade pip
                    pip install -r requirements.txt
                    pip install -r requirements-test.txt
                    '''
                }
            }
        }
        
        stage('Automated Tests (Testcontainers)') {
            steps {
                dir('backend-aks/brain/dashboard-soc') {
                    // Testcontainers se encargará de contactar al demonio Docker en /var/run/docker.sock
                    // Descargará mongo:6.0, levantará la base de datos y ejecutará la validación
                    sh 'pytest tests/ -v'
                }
            }
        }
    }
    
    post {
        always {
            // Se ejecuta sin importar si las pruebas pasaron o fallaron.
            // El contenedor limpiador "Ryuk" de Testcontainers garantiza que el MongoDB efímero muera.
            echo 'Limpiando entorno y finalizando Pipeline SATRI-CI.'
        }
        success {
            echo 'Pruebas exitosas. Listo para integración continua o despliegue.'
        }
        failure {
            echo 'Las pruebas fallaron. Revisa los logs de Testcontainers y pytest.'
        }
    }
}
