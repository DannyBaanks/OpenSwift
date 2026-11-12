import SwiftUI

struct Dashboard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Resumen")
                .font(.system(size: 30, weight: .bold))
                .foregroundColor(.white)
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Builds")
                        .font(.system(size: 12))
                        .foregroundColor(.gray)
                    Text("14")
                        .font(.system(size: 26, weight: .semibold))
                        .foregroundColor(.white)
                }
                .padding(14)
                .background(Color.gray)
                .cornerRadius(14)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Previews")
                        .font(.system(size: 12))
                        .foregroundColor(.gray)
                    Text("32")
                        .font(.system(size: 26, weight: .semibold))
                        .foregroundColor(.white)
                }
                .padding(14)
                .background(Color.gray)
                .cornerRadius(14)
            }
            Spacer()
            Button("Nueva sesión") { }
                .frame(maxWidth: .infinity)
                .frame(height: 46)
        }
        .padding(20)
        .background(Color.black)
    }
}
