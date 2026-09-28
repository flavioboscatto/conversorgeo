import math

# ==============================================================================
# MOTOR GEODÉSICO (MANTIDO INTACTO)
# ==============================================================================
class MotorGeodesico:
    a = 6378137.0
    f = 1.0 / 298.257222101
    b = a * (1.0 - f)
    e2 = (a**2 - b**2) / (a**2)
    ep2 = (a**2 - b**2) / (b**2)
    k0 = 0.9996

    @classmethod
    def lat_lon_para_utm(cls, lat, lon, fuso, hemisferio):
        lat_rad = math.radians(lat)
        fuso_num = int(fuso)
        lon0_deg = (fuso_num * 6) - 183
        lon0_rad = math.radians(lon0_deg)
        dlon = math.radians(lon) - lon0_rad

        N = cls.a / math.sqrt(1.0 - cls.e2 * math.sin(lat_rad)**2)
        T = math.tan(lat_rad)**2
        C = cls.ep2 * math.cos(lat_rad)**2
        A = dlon * math.cos(lat_rad)

        M = cls.a * (
            (1.0 - cls.e2/4.0 - 3.0*cls.e2**2/64.0 - 5.0*cls.e2**3/256.0) * lat_rad -
            (3.0*cls.e2/8.0 + 3.0*cls.e2**2/32.0 + 45.0*cls.e2**3/1024.0) * math.sin(2.0*lat_rad) +
            (15.0*cls.e2**2/256.0 + 45.0*cls.e2**3/1024.0) * math.sin(4.0*lat_rad) -
            (35.0*cls.e2**3/3072.0) * math.sin(6.0*lat_rad)
        )

        east = cls.k0 * N * (
            A + (1.0 - T + C) * A**3 / 6.0 +
            (5.0 - 18.0 * T + T**2 + 72.0 * C - 58.0 * cls.ep2) * A**5 / 120.0
        ) + 500000.0

        north = cls.k0 * (
            M + N * math.tan(lat_rad) * (
                A**2 / 2.0 +
                (5.0 - T + 9.0 * C + 4.0 * C**2) * A**4 / 24.0 +
                (61.0 - 58.0 * T + T**2 + 600.0 * C - 330.0 * cls.ep2) * A**6 / 720.0
            )
        )
        if hemisferio == 'S' or (lat < 0 and hemisferio == 'S'):
            if north < 0: north += 10000000.0
            elif north < 5000000.0: north += 10000000.0

        return east, north

    @classmethod
    def utm_para_lat_lon(cls, east, north, fuso, hemisferio):
        x = east - 500000.0
        y = north - 10000000.0 if hemisferio == 'S' else north

        fuso_num = int(fuso)
        lon0_deg = (fuso_num * 6) - 183
        lon0_rad = math.radians(lon0_deg)

        e1 = (1.0 - math.sqrt(1.0 - cls.e2)) / (1.0 + math.sqrt(1.0 - cls.e2))
        M = y / cls.k0
        mu = M / (cls.a * (1.0 - cls.e2/4.0 - 3.0*cls.e2**2/64.0 - 5.0*cls.e2**3/256.0))

        phi1_rad = (mu +
                    (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0) * math.sin(2.0 * mu) +
                    (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0) * math.sin(4.0 * mu) +
                    (151.0 * e1**3 / 96.0) * math.sin(6.0 * mu) +
                    (1097.0 * e1**4 / 512.0) * math.sin(8.0 * mu))

        N1 = cls.a / math.sqrt(1.0 - cls.e2 * math.sin(phi1_rad)**2)
        R1 = cls.a * (1.0 - cls.e2) / (1.0 - cls.e2 * math.sin(phi1_rad)**2)**1.5
        D = x / (N1 * cls.k0)

        T1 = math.tan(phi1_rad)**2
        C1 = cls.ep2 * math.cos(phi1_rad)**2

        lat_rad = phi1_rad - (N1 * math.tan(phi1_rad) / R1) * (
            D**2 / 2.0 -
            (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * C1**2 - 9.0 * cls.ep2) * D**4 / 24.0 +
            (61.0 + 90.0 * T1 + 298.0 * C1 + 45.0 * T1**2 - 252.0 * cls.ep2 - 3.0 * C1**2) * D**6 / 720.0
        )

        lon_rad = lon0_rad + (
            D -
            (1.0 + 2.0 * T1 + C1) * D**3 / 6.0 +
            (5.0 - 2.0 * C1 + 28.0 * T1 - 3.0 * C1**2 + 8.0 * cls.ep2 + 24.0 * T1**2) * D**5 / 120.0
        ) / math.cos(phi1_rad)

        return math.degrees(lat_rad), math.degrees(lon_rad), cls.k0 * (1.0 + (D**2 / 2.0) * (1.0 + C1)), math.degrees(math.sin(phi1_rad) * D)

    @staticmethod
    def decimal_para_sexagesimal(graus_dec, suf_pos, suf_neg):
        sufixo = suf_pos if graus_dec >= 0 else suf_neg
        abs_graus = abs(graus_dec)
        g = int(abs_graus)
        m_resto = (abs_graus - g) * 60.0
        m = int(m_resto)
        s = (m_resto - m) * 60.0
        if s >= 59.99999:
            s = 0.0
            m += 1
            if m >= 60:
                m = 0
                g += 1
        return f"{g:02d}°{m:02d}'{s:07.4f}\"{sufixo}"

    @staticmethod
    def sexagesimal_para_decimal(txt_ggmmss):
        try:
            txt = txt_ggmmss.strip()
            if not txt:
                raise ValueError("String vazia")
            
            txt_upper = txt.upper()
            sinal = 1.0
            if txt_upper.startswith("-") or txt_upper.endswith("S") or txt_upper.endswith("W"):
                sinal = -1.0
                
            txt_clean = txt_upper.strip("+-NSEW \t")
            
            for char in ["º", "°", "'", '"', "”", "“", "|"]:
                txt_clean = txt_clean.replace(char, " ")
            
            # Divide por espaços e remove vazios e vírgulas residuais
            initial_tokens = [t.strip(", \t") for t in txt_clean.split() if t.strip(", \t")]
            
            if not initial_tokens:
                raise ValueError("Nenhum valor numérico encontrado")
            
            if len(initial_tokens) == 1:
                # Caso de token único (ex: -27,30300404 ou -27.30300404 ou -27,3030.0404)
                single_str = initial_tokens[0]
                if "," in single_str:
                    tokens = single_str.split(",")
                elif "." in single_str:
                    tokens = single_str.split(".", 1)
                else:
                    tokens = [single_str]
            else:
                tokens = initial_tokens
                
            if len(tokens) >= 3:
                graus = float(tokens[0])
                minutos = float(tokens[1])
                segundos = float(tokens[2].replace(",", "."))
            elif len(tokens) == 2:
                graus = float(tokens[0])
                bloco = tokens[1]
                
                if "." in bloco:
                    bloco_pad = bloco.zfill(7)
                    minutos = float(bloco_pad[:2])
                    segundos = float(bloco_pad[2:])
                else:
                    bloco_pad = bloco.zfill(8)
                    minutos = float(bloco_pad[:2])
                    segundos = float(bloco_pad[2:4] + "." + bloco_pad[4:])
            elif len(tokens) == 1:
                graus = float(tokens[0])
                minutos = 0.0
                segundos = 0.0
            else:
                raise ValueError("Formato não reconhecido")
                
            return (graus + (minutos / 60.0) + (segundos / 3600.0)) * sinal
        except Exception:
            raise ValueError(f"Formato Sexagesimal inválido: {txt_ggmmss}")