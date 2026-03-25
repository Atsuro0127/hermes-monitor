import json, datetime, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

raw_tweets = [
  {"tweetId":"2036290813219709350","username":"antoshia2n","displayName":"シアニン｜言語化コンサル","text":"質問しないのが、一番の損失と知って欲しい、","likes":45689,"retweets":748,"replies":93,"quotes":250},
  {"tweetId":"2036082962677284937","username":"bcg_acn","displayName":"戦略コンサル総合コンサル","text":"友人に学生時代からパチスロで稼ぎ、まだ儲かった時代のアフィリエイトで当ててFI達成した人がいますが、\n\nこういう人たちの「死んだ魚の目のサラリーマンにだけはなりたくない」というモチベーションの強さは尋常じゃない\n\n寝食惜しんでサイト構築するのはまさに怠惰を求めて勤勉に行きつく様そのもの","likes":81372,"retweets":678,"replies":55,"quotes":232},
  {"tweetId":"2036069702506848662","username":"bcg_acn","displayName":"戦略コンサル総合コンサル","text":"コンサルの仕事をするようになって気づいたnewな発見の一つが、世の中には物事を決められない大人がこんなに沢山いるのかということ\n\n若いうちに権限与えられなかった人は、決めなきゃいけない年齢になった時には見事に「仕上がっている」ので、まあ背中押すの大変","likes":62942,"retweets":659,"replies":82,"quotes":132},
  {"tweetId":"2011665545247277456","username":"oef4raF1ZW3D4WI","displayName":"賈詡","text":"地方に至っては国から金もらっても何に使っていいか知恵がないから、デロイトとかアクセンチュアのコンサルに頼んで使い道を考えてもらう始末だ\n\nコンサル何かに頼って成果が出たためしがねえ。訳のわからんIT化とかアプリの開発とかそんなのばっかりやで","likes":49951,"retweets":1310,"replies":365,"quotes":45},
  {"tweetId":"2035481311096553578","username":"narisumashi100","displayName":"なりすましコンサル","text":"純文学はハードル高そうに見えるけど、読むと普通に面白いです\n\n初心者はこの辺から始めるのが読みやすいのでおすすめよ\n\n・夏目漱石：こころ\n・芥川龍之介：鼻、地獄変\n・太宰治：人間失格\n・川端康成：雪国\n・三島由紀夫：金閣寺","likes":3253,"retweets":1427,"replies":63,"quotes":9312},
  {"tweetId":"2034622675612840320","username":"antoshia2n","displayName":"シアニン｜言語化コンサル","text":"No No Girlsのオーディション見た人はめちゃくちゃ参考になるはず。人を育てる本質っていつの時代も同じ。","likes":2564,"retweets":320,"replies":2,"quotes":3437},
  {"tweetId":"2028013671205769531","username":"Komatsuna_56789","displayName":"ゆる外資コンサルMom","text":"割とコンサル界隈でも聞く話。\n女性管理職の方が1日のスケジュールを新卒研修で見せてくれた。子供がいても管理職できるよというのを主張したかったみたいなんだけど、9時に子供と就寝、2時に起床して仕事をしてそこから子育てして出勤してるのを見て怖くて新卒の女子一同無言になった覚えがある。","likes":1828,"retweets":2719,"replies":138,"quotes":22653},
  {"tweetId":"1982235719729901805","username":"hikarin22","displayName":"ひかりん＠婚活コンサル","text":"ADHDはコンサルとかSIerとかプロジェクト型のお仕事が向いてるんよね。もしくは反対に頭を全く使わない本当に完全なる単純作業。あと意外だけどマネージャーも結構向いてるんですよね。","likes":1513,"retweets":405,"replies":7,"quotes":3907},
  {"tweetId":"2036037455187681649","username":"yusaku_0426","displayName":"yusaku｜PM/コンサル/AI","text":"Claude Codeを業務に使う上でやっておくべき 7つのセキュリティ設定","likes":1110,"retweets":87,"replies":3,"quotes":865},
  {"tweetId":"2036073954029314369","username":"bcg_acn","displayName":"戦略コンサル総合コンサル","text":"私マネージャー上がった時には、パートナーから「後輩の資料はどう修正するかではなく、どう活かせるかまず考えろ」と言われたんですが、\n\nそれもそうか。と思い実践した結果気づいたこととして、自分だいぶ偏見で資料見てたんだなという事","likes":947,"retweets":150,"replies":6,"quotes":2084},
  {"tweetId":"2034927330200826085","username":"antoshia2n","displayName":"シアニン｜言語化コンサル","text":"疲れやすい人は、ハードな運動とか逆効果なので、まずはコレから試して欲しい。","likes":1238,"retweets":401,"replies":4,"quotes":3006},
  {"tweetId":"2035650745798893954","username":"yuoku4619","displayName":"熊コンサル","text":"言い方はともかく、当時の社内では深刻な問題になっていた。特に今までパッと伝わってた事が伝わらずに社内全体でストレスが蓄積してた。\n・指示が一回で理解できない\n・語彙力がなく簡易な表現が必要\n・数字が計算できず、そこを理解させるのに30分必要\n・文章能力が無さすぎて資料作成できない","likes":750,"retweets":300,"replies":15,"quotes":2394},
  {"tweetId":"2036015875573359031","username":"narisumashi100","displayName":"なりすましコンサル","text":"若手は、仮説やストーリーで上司に勝つのはなかなか難しい。経験値の差が出る領域なので\n\nじゃあ勝てる領域はどこかというと、\n一次情報です\n\n現場でしか取れないファクトを泥臭く集めに行く\n\nここは経験ではなく、情報を取りに行った人が勝つので、一次情報で上司や顧客を殴りにいきましょう","likes":599,"retweets":220,"replies":11,"quotes":1945},
  {"tweetId":"2035208088979206611","username":"nmmg091","displayName":"なまむぎ@コンサル","text":"帰りの電車内の15分はスマホのメモ機能でその日のパフォーマンスを「内省」するのがオススメ。\nやり方としては超細かい事柄ひとつを深掘る。続ければ1年で300近い学びが蓄積される。","likes":634,"retweets":139,"replies":1,"quotes":1407},
  {"tweetId":"2035570244123816065","username":"bcg_acn","displayName":"戦略コンサル総合コンサル","text":"わたしもこれは至言だと思います\nファームで何度も助けてくれた言葉\n\n10分考えても明かりが見えない時は\n・誤った問いに取り組んでいる\n・少なくとも今の自分単独では答えを出せない問いである\n\nと考えて、\n他人に相談するか、いったん別のことを考えるか、のアクションを取るように心がけていました","likes":463,"retweets":76,"replies":1,"quotes":1096},
  {"tweetId":"2036388822527905938","username":"bcg_acn","displayName":"戦略コンサル総合コンサル","text":"BCGのようなトップファームのプロジェクトが、1日単位で超速で進む本当の理由は「ボールを止める人がほぼゼロ」だからなんですよね\n\n現場で実際に回していると、以下ポイントが徹底されています：\n・他人に動いてもらう必要があることは、即依頼して待たせない","likes":427,"retweets":60,"replies":5,"quotes":773},
  {"tweetId":"2034979869772202140","username":"narisumashi100","displayName":"なりすましコンサル","text":"言語化レベルを上げるためには、「正しく美しい日本語を知る」ことが何より大事","likes":556,"retweets":248,"replies":11,"quotes":1864},
  {"tweetId":"2034764475933630734","username":"antoshia2n","displayName":"シアニン｜言語化コンサル","text":"地頭の正体はコレでした。","likes":684,"retweets":226,"replies":8,"quotes":1525},
  {"tweetId":"2036376726666875190","username":"narisumashi100","displayName":"なりすましコンサル","text":"私がまだコンサルになりすましたての頃、\n\n一次情報を収集するために、顧客の店の前で一日中立って、店に入る方200人くらいにアンケートを取ったことがあります","likes":308,"retweets":143,"replies":11,"quotes":1530},
  {"tweetId":"2034986165867356459","username":"nmmg091","displayName":"なまむぎ@コンサル","text":"監査からコンサルに転職するなら、プロマネを学ぶことが必須。スコープ、ゴールが固定され、前期調書があってタスクが見える内向きの会計監査なんてプロジェクトでもなんでもないからね。転職してから死ぬぞ。","likes":544,"retweets":37,"replies":2,"quotes":674},
  {"tweetId":"2035914957884412010","username":"escapejapan2023","displayName":"マンション好きの外資コンサル","text":"確かにAIで限界費用が下がり続けるならこの前提は壊れる。\n「既存の通貨制度が続く」「労働による所得が存在する」という前提の上に立っている。その前提を疑わずに「株と債券の比率をどうするか」を議論しているのは、沈みゆく船の中で座席を替えているようなものだ。","likes":630,"retweets":75,"replies":3,"quotes":743},
  {"tweetId":"2035369167503904925","username":"mid_level_cons","displayName":"中堅コンサル","text":"まあ、私がいくらポストしたところで、ファームの課題図書とか、一般的な推薦本は、読む人は言われなくても読むし、読まない人は、誰が何度口酸っぱく言っても読まないので無駄なのでしょう。\n\n一応、会計とか、知らないと即死する系の本だけ挙げときます。","likes":1017,"retweets":44,"replies":4,"quotes":678},
  {"tweetId":"2036056238690353579","username":"narisumashi100","displayName":"なりすましコンサル","text":"これ、めちゃくちゃ良いアナリストの動きだと思います\n\n議論中にファクトや過去討議資料などが一瞬で出てくるだけで、他の方は思考と討議にフル集中できる\n\n地味に見えてプロジェクトの生産性を底上げする立派な付加価値","likes":382,"retweets":61,"replies":5,"quotes":871},
  {"tweetId":"2035365899881066871","username":"cr7_consultant","displayName":"ロナウド@駆け出しコンサル","text":"デロイトグループの社員は、監査法人トーマツが監査をしているSBI証券の証券口座を作ることや、三菱UFJアセットマネジメントの投資商品を購入することはできませんね。","likes":410,"retweets":189,"replies":10,"quotes":1173},
  {"tweetId":"2034599307694027060","username":"sub_consultant","displayName":"とり@コンサル","text":"SIer出身のコンサルな先輩が言ってたんだけど、\nSIerは導入するシステムの要件を決めて開発を進める。つまり顧客から要件を聞き出すことに重きを置く。なので、顧客が答えを持っており、それを出してもらおうという意識になる。ある意味で言うと受け身の姿勢。\nコンサルだと違う","likes":500,"retweets":99,"replies":7,"quotes":708},
  {"tweetId":"2032729426740588769","username":"hirokinose","displayName":"野瀬大樹","text":"割とこれは本当で本邦の「仕事」の8割くらいは「誰の責任にもならないため」のものだと思ってる。\n一時期「コンサル」が流行っていたのもあれは「責任のアウトソーシング」をするため。","likes":248,"retweets":393,"replies":6,"quotes":1614},
  {"tweetId":"2034995160036384779","username":"bcg_acn","displayName":"戦略コンサル総合コンサル","text":"私この業界入ってからはずっと、電車乗ったときはiPhoneの純正メモで頭整理してるんですが、これ言語化能力鍛える上で結構オススメですよ\n\nフリック入力だと長文書く気にならない → 強制的に短く端的にまとめる癖がつく","likes":345,"retweets":48,"replies":3,"quotes":597},
  {"tweetId":"2036097143841452070","username":"escapejapan2023","displayName":"マンション好きの外資コンサル","text":"悪いこと言わんから住宅ローンで自宅買っておくのはやっておいた方がいい。\n\n投資物件まで無理に手を出す必要はないけど自宅だけは買うべき。","likes":370,"retweets":158,"replies":8,"quotes":1409},
  {"tweetId":"1901926580672450940","username":"consultnt_a","displayName":"とあるコンサルタント","text":"官僚出身のコンサル転職者、初期からラストマンシップがマックスで入ってくるのですげー頼れるんだよな\nあとブラック労働に対する耐性が強すぎてコンサル環境でもホワイトすぎるとかよく言ってる","likes":277,"retweets":166,"replies":13,"quotes":1583},
  {"tweetId":"2036547000716632357","username":"Komatsuna_56789","displayName":"ゆる外資コンサルMom","text":"同時期くらいに産休に入った同僚、まさかの4月入園の申請し忘れで保育園に入れず、復帰予定が白紙。4月入園は前年度の10月くらいに締切なのを知らなかった模様。","likes":350,"retweets":253,"replies":102,"quotes":2140},
  {"tweetId":"2036038960418578703","username":"antoshia2n","displayName":"シアニン｜言語化コンサル","text":"先延ばしは脳の使い方を知るだけで減らせるんです。","likes":483,"retweets":128,"replies":1,"quotes":859},
  {"tweetId":"2034594092274106483","username":"antoshia2n","displayName":"シアニン｜言語化コンサル","text":"パフォーマンスが安定してるシゴデキの正体はこれ","likes":205,"retweets":55,"replies":1,"quotes":556},
  {"tweetId":"2035483122180256140","username":"narisumashi100","displayName":"なりすましコンサル","text":"純文学を読むメリットは\n\n・読解力/想像力/語彙力/表現力の向上\n・行間を読む力/深い洞察力の養成\n・人間理解の深化\n\nなどいろいろありますが、単純に読み物として面白く、人生が豊かになる感じがするのよね","likes":224,"retweets":88,"replies":4,"quotes":1034},
]

articles = []
for t in raw_tweets:
    eng = t['likes'] + t['retweets']*2 + t.get('quotes',0) + t.get('replies',0)
    articles.append({
        'articleId': t['tweetId'],
        'tweetId': t['tweetId'],
        'tweetUrl': f"https://x.com/{t['username']}/status/{t['tweetId']}",
        'lang': 'ja',
        'title': t['text'].split('\n')[0][:80],
        'body': t['text'],
        'preview': t['text'][:140],
        'thumbnail': '',
        'author': {'name': t['displayName'], 'screenName': t['username'], 'bio': '', 'followersCount': 0},
        'stats': {'likes': t['likes'], 'retweets': t['retweets'], 'replies': t.get('replies',0),
                  'quotes': t.get('quotes',0), 'bookmarks': 0, 'views': 0},
        'engagementScore': eng,
        'createdAt': '',
        'source': 'tweet_only',
    })

articles.sort(key=lambda a: a['engagementScore'], reverse=True)
ts = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')
out = f'output/report-consult-{ts}.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)
print(f'{len(articles)}件保存: {out}')
print(out)
