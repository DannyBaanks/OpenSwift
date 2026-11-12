import SwiftUI

struct Settings: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Ajustes")
                .font(.system(size: 30, weight: .bold))
            HStack {
                Label("Modo avión", systemImage: "airplane")
                Spacer()
                Text("Off")
            }
            Divider()
            HStack {
                Label("Notificaciones", systemImage: "bell")
                Spacer()
                Text("On")
            }
            Divider()
            HStack {
                Label("Sincronizar", systemImage: "arrow.triangle.2.circlepath")
                Spacer()
                Text("Wi-Fi")
            }
            Spacer()
            Button("Cerrar sesión") { }
                .frame(maxWidth: .infinity)
                .frame(height: 44)
        }
        .padding(20)
    }
}
