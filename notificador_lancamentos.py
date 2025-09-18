import os
import requests
from itertools import groupby
import datetime
from operator import itemgetter

# --- CONFIGURAÇÕES Lidas de um local seguro ---
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# --- FUNÇÕES ---

def send_telegram_message(message):
    """Envia uma mensagem para o chat especificado no Telegram."""
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(api_url, json=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"Erro ao enviar mensagem para o Telegram: {e}")
        return False

def get_movie_releases(start_date, end_date):
    """Busca lançamentos de filmes no TMDB em um intervalo de datas."""
    url = f"https://api.themoviedb.org/3/discover/movie"
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'pt-BR',
        'region': 'BR',
        'primary_release_date.gte': start_date,
        'primary_release_date.lte': end_date,
        'sort_by': 'popularity.desc'
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        movies = response.json().get('results', [])
        return [f"- {movie['title']} ({movie['release_date']})" for movie in movies]
    return []

def format_episode_ranges(episodes_by_season):
    """Formata os números de episódios em SXX EXX-YY."""
    parts = []
    for season, episodes in sorted(episodes_by_season.items()):
        if not episodes:
            continue
        
        season_str = f"S{str(season).zfill(2)}"
        sorted_episodes = sorted(list(set(episodes)))
        
        # Agrupa números consecutivos
        ranges = []
        for k, g in groupby(enumerate(sorted_episodes), lambda i_x: i_x[0] - i_x[1]):
            group = list(map(itemgetter(1), g))
            if len(group) > 1:
                ranges.append(f"E{str(group[0]).zfill(2)}-{str(group[-1]).zfill(2)}")
            else:
                ranges.append(f"E{str(group[0]).zfill(2)}")
        parts.append(f"{season_str} {', '.join(ranges)}")
    return ", ".join(parts)

def get_tv_show_episodes(start_date, end_date):
    """Busca séries com episódios no ar e encontra os números específicos."""
    print("Iniciando busca por séries... (pode demorar um pouco)")
    # 1. Descobrir quais séries tiveram episódios no período
    discover_url = f"https://api.themoviedb.org/3/discover/tv"
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'pt-BR',
        'air_date.gte': start_date,
        'air_date.lte': end_date,
        'sort_by': 'popularity.desc'
    }
    response = requests.get(discover_url, params=params)
    if response.status_code != 200:
        return []

    discovered_series = response.json().get('results', [])
    formatted_series_list = []

    # 2. Para cada série, buscar os detalhes e encontrar os episódios exatos
    for series in discovered_series:
        series_id = series['id']
        series_name = series['name']
        first_air_year = series.get('first_air_date', '???')[:4]
        print(f"  -> Verificando episódios de: {series_name}")

        details_url = f"https://api.themoviedb.org/3/tv/{series_id}?api_key={TMDB_API_KEY}&language=pt-BR"
        details_response = requests.get(details_url)
        if details_response.status_code != 200:
            continue
        
        seasons = details_response.json().get('seasons', [])
        episodes_by_season = {}

        # 3. Itera sobre as temporadas para encontrar os episódios que batem com a data
        for season in seasons:
            # Ignora temporadas "especiais" (season_number 0)
            if season['season_number'] == 0:
                continue

            season_url = f"https://api.themoviedb.org/3/tv/{series_id}/season/{season['season_number']}?api_key={TMDB_API_KEY}&language=pt-BR"
            season_response = requests.get(season_url)
            if season_response.status_code != 200:
                continue

            episodes_data = season_response.json().get('episodes', [])
            for episode in episodes_data:
                air_date = episode.get('air_date')
                if air_date and start_date <= air_date <= end_date:
                    season_num = episode['season_number']
                    ep_num = episode['episode_number']
                    if season_num not in episodes_by_season:
                        episodes_by_season[season_num] = []
                    episodes_by_season[season_num].append(ep_num)

        if episodes_by_season:
            episode_str = format_episode_ranges(episodes_by_season)
            formatted_series_list.append(f"- {series_name} ({first_air_year}) - {episode_str}")

    return formatted_series_list

def main(time_period):
    """Função principal que busca e envia as notificações."""
    today = datetime.date.today()
    if time_period == 'dia':
        start_date = today
        title = "Lançamentos de Hoje"
    elif time_period == 'semana':
        start_date = today - datetime.timedelta(days=7)
        title = "Lançamentos da Semana"
    elif time_period == 'mes':
        start_date = today - datetime.timedelta(days=30)
        title = "Lançamentos do Mês"
    else:
        print("Período inválido. Use 'dia', 'semana' ou 'mes'.")
        return

    end_date_str = today.strftime('%Y-%m-%d')
    start_date_str = start_date.strftime('%Y-%m-%d')

    print(f"Buscando lançamentos de {start_date_str} até {end_date_str}...")

    movies = get_movie_releases(start_date_str, end_date_str)
    tv_shows = get_tv_show_episodes(start_date_str, end_date_str)

    message = f"*{title} ({start_date_str})*\n\n"
    
    if movies:
        message += "*🎬 Filmes Lançados*\n"
        message += "\n".join(movies)
        message += "\n\n"
    
    if tv_shows:
        message += "*📺 Novidades em Séries*\n"
        message += "\n".join(tv_shows)
        message += "\n\n"

    if not movies and not tv_shows:
        message += "Nenhum lançamento popular encontrado no período."

    print("Enviando mensagem para o Telegram...")
    if not send_telegram_message(message):
        print("Falha ao enviar a mensagem.")
    else:
        print("Mensagem enviada com sucesso!")

if __name__ == '__main__':
    # Altere aqui para 'dia', 'semana' ou 'mes' conforme sua necessidade
    periodo_desejado = 'dia' 
    main(periodo_desejado)