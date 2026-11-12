import SwiftUI

struct Login: View {
    var body: some View {
        VStack(spacing: 16) {
            Spacer()
            Text("Bienvenido")
                .font(.system(size: 28, weight: .bold))
            Text("Entra para seguir diseñando")
                .font(.system(size: 14))
                .foregroundColor(.gray)
            TextField("Correo", text: $email)
            SecureField("Contraseña", text: $password)
            Button("Entrar") { }
                .frame(maxWidth: .infinity)
                .frame(height: 48)
                .background(Color.blue)
                .cornerRadius(12)
            Spacer()
        }
        .padding(24)
    }
}
